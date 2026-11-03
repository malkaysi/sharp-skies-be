# Stack Worker Spec

Move the video-stacking pipeline out of the FastAPI `/api/stack` route and into
an SQS-triggered container Lambda, so heavy jobs run in isolation and many
users can stack videos at the same time.

## Where we left off (2026-11-02)

**Done:** M0 and M1. The real pipeline runs in the Lambda container locally
(branch `lambda-m1`). `run_stack()` in `app/services/stack_pipeline.py` is
shared by the Render route and the Lambda handler. Local results (Mac,
`--memory=2g`):

| Video | Frames (scored / selected) | Time | Peak RSS (fresh process) |
|---|---|---|---|
| `moon2.mp4` 22.4MB | 237 / 47 (matches Render) | 15.5s | 461MB |
| `IMG_2036.MOV` 5.7MB HEVC | 316 / 63 | 21.5s | 543MB — can never fit Render's 512MB |

Also verified: a local request to `/api/stack` through the refactored route
(frontend → uvicorn, `moon2.mp4`: 237/47 frames, 200 OK, same response shape).

How to run it locally: see "Running the worker locally" below.

**Done: M2 — AWS resources** (2026-11-02, region `us-east-2`, account
`277775957682`). Mix of CLI and console; all verified with the CLI.

| Resource | Details | Identifier |
|---|---|---|
| S3 bucket | Public access blocked, SSE-S3, lifecycle `expire-job-files` = 7 days | `sharp-skies-stack-277775957682` |
| DynamoDB `stack_jobs` | PK `job_id` (String), on-demand, TTL on `expires_at` | `arn:aws:dynamodb:us-east-2:277775957682:table/stack_jobs` |
| ECR `stack-worker` | Mutable tags, AES256 | `277775957682.dkr.ecr.us-east-2.amazonaws.com/stack-worker` |
| IAM role `stack-worker-role` | Trusts `lambda.amazonaws.com`; `AWSLambdaBasicExecutionRole` + inline `stack-worker-access` (S3 GetObject `uploads/*`, PutObject `results/*`; DynamoDB GetItem/UpdateItem on `stack_jobs`) | `arn:aws:iam::277775957682:role/stack-worker-role` |
| Budget alert | Monthly cost budget, $15 | `Monthly Budget` |

Retention decided: 7 days (open question 4). SQS permissions get added to the
role in M4; S3 CORS in M5.

**Next: M3 — deployed, manually invoked.**
- Handler: read `{job_id, top_percent}`, download `uploads/{job_id}.<ext>`
  from S3 to `/tmp`, run `run_stack`, upload `results/{job_id}.png`, update
  the `stack_jobs` row (`processing` → `done`/`failed`, stats, timestamps).
  Needs `boto3` (already in the Lambda Python runtime, but pin it in
  `requirements.txt` for parity).
- Build the image (arm64), log Docker into ECR, tag and push.
- Create the Lambda function from the image: architecture **arm64**, role
  `stack-worker-role`, memory 2048MB, timeout 5 min, ephemeral storage 2GB.
- Test: upload a reference video to `uploads/` by hand, put a job row in
  `stack_jobs`, invoke from the console, check `results/` and the row. Record
  the real Lambda duration and Max Memory Used for both reference videos.

Nothing gets created in AWS without an explicit go-ahead.

### Running the worker locally
From the repo root, with Docker running and videos in `test-videos/`:

```bash
docker build -f lambdas/stack_worker/Dockerfile -t stack-worker .
docker run --rm -p 9000:8080 --memory=2g -e AWS_LAMBDA_FUNCTION_TIMEOUT=900 -e OUTPUT_DIR=/output -v "$PWD/test-videos:/videos:ro" -v "$PWD/test-output:/output" stack-worker
# second terminal:
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{"video_path": "/videos/moon2.mp4", "top_percent": 0}'
```

Start it from the terminal, not Docker Desktop's Run button (that skips the
port, volumes and env). Restart between runs for clean `peak_rss` numbers —
a warm container carries over its high-water mark, just like real Lambda.

## Problem

`POST /api/stack` (`app/routes/stack.py`) runs 30s–2min of CPU/memory-heavy
OpenCV work inside the web request on a single Render instance:

- Large videos have caused OOM kills and native segfaults, taking the whole API
  down with them.
- `_cv2_pipeline_lock` serializes all stacking, so concurrent users queue
  behind each other inside one process (and hold the HTTP connection open the
  whole time).
- The raw upload is read fully into API memory.

## Goals

1. A stacking job can never crash or stall the API.
2. Multiple users can stack at once, each in their own isolated environment.
3. Same output as today: stacked PNG + `frames_total`, `frames_selected`,
   `top_percent`, `elapsed_ms`.
4. Reuse the existing pipeline code (`app/services/*`) — no fork of the
   algorithm.

## Non-goals

- Changing the stacking algorithm or quality.
- Moving `/enhance` or `/background` to Lambda (revisit later if needed).
- Real-time progress percentages (status states are enough for v1).

## Target architecture

```
Browser ──1. POST /api/jobs──────────────▶ API (Render)
        ◀── job_id + presigned upload URL ─┘   │ creates job row (status=pending_upload)
        ──2. PUT video ───────────────────▶ S3  uploads/{job_id}.mp4
        ──3. POST /api/jobs/{id}/start ───▶ API ── sends {job_id, top_percent} ──▶ SQS
                                                                                  │
                                         Lambda (stack_worker) ◀──────────────────┘
                                           - status=processing
                                           - download uploads/{job_id}.mp4 → /tmp
                                           - run pipeline
                                           - upload results/{job_id}.png
                                           - status=done + stats  (or failed + error)
        ──4. GET /api/jobs/{id} (poll) ───▶ API ── reads job row
        ◀── status, stats, presigned result URL when done
```

The browser uploads straight to S3 via a presigned URL, so the video never
passes through API memory.

### Components

| Component | Choice | Notes |
|---|---|---|
| Worker | Lambda, container image (`public.ecr.aws/lambda/python:3.13`) | Container needed for OpenCV/numpy size |
| Queue | SQS standard queue, batch size **1** | One video per invocation |
| Dead-letter queue | SQS DLQ, `maxReceiveCount` = 2 | Poison videos stop retrying |
| Storage | One S3 bucket, `uploads/` and `results/` prefixes | Lifecycle rule deletes both after N days |
| Job status | DynamoDB table `stack_jobs`, PK `job_id` | On-demand billing |
| Image registry | ECR repo `stack-worker` | |

### Job record (`stack_jobs`)

| Field | Type | Notes |
|---|---|---|
| `job_id` | string (uuid4) | PK |
| `status` | `pending_upload` \| `queued` \| `processing` \| `done` \| `failed` | |
| `top_percent` | number | From request |
| `filename` | string | Original name, for download naming |
| `result_key` | string | `results/{job_id}.png`, set when done |
| `frames_total`, `frames_selected`, `top_percent_actual`, `elapsed_ms` | number | Set when done |
| `error` | string | Set when failed (user-safe message) |
| `created_at`, `updated_at` | ISO string | |
| `queued_at`, `started_at`, `finished_at` | ISO string | Stage timestamps for end-to-end timing |
| `phase_ms` | map | Per-phase worker timings: `download`, `score`, `align_stack`, `upload` |
| `expires_at` | epoch number | DynamoDB TTL |

### API contract (replaces `POST /api/stack`)

- `POST /api/jobs` — body `{filename, top_percent}` → `{job_id, upload_url}`.
  Validates `top_percent` in [0, 100] (same rule as today).
- `POST /api/jobs/{job_id}/start` → `202 {job_id, status: "queued"}`.
  Rejects if the upload object doesn't exist.
- `GET /api/jobs/{job_id}` → `{status, ...stats, result_url?, error?}`.
  `result_url` is a short-lived presigned GET for the PNG.

### Lambda configuration (starting values, tune with real videos)

- Memory: 3008 MB (also buys more CPU); raise toward 10 GB if peak RSS needs it
- Timeout: 5 min (pipeline is 30s–2min today); SQS visibility timeout ≥ 6× this
- Ephemeral storage (`/tmp`): 2 GB
- Reserved concurrency: 5 to start — caps cost and protects the account limit
- `cv2.setNumThreads(1)` is no longer required (no shared process) — benchmark
  with OpenCV threading on, since Lambda gets multiple vCPUs at higher memory

## Milestones

Each milestone ends with something you can run and check.

### M0 — Hello-world container ✅
Handler + Dockerfile run under the Lambda Runtime Interface Emulator locally.

### M1 — Real pipeline, local file ✅
- Docker build context = repo root; image copies `app/services/` and installs
  the pipeline deps (`numpy`, `opencv-python-headless`, `pillow`).
- Extract the pipeline body of `stack_video` into a plain function, e.g.
  `run_stack(data, filename, top_percent) -> (png_bytes, stats)` in
  `app/services/`, used by both the route and the Lambda.
- Handler accepts `{"video_path": "/tmp/test.mp4", "top_percent": 10}` and
  writes the PNG to `/tmp`.

**Done when:** invoking the emulator with a test video mounted into the
container produces the same PNG/stats as the current `/api/stack` route.

### M2 — AWS resources
S3 bucket (with lifecycle rule), DynamoDB table (with TTL), ECR repo, IAM role
for the Lambda (S3 read `uploads/*`, write `results/*`; DynamoDB update on
`stack_jobs`; CloudWatch logs; SQS consume).

**Done when:** resources exist and are written down (console steps or IaC —
see open questions).

### M3 — Deployed, manually invoked
- Handler reads `{job_id, top_percent}`, downloads from S3, runs `run_stack`,
  uploads result, updates DynamoDB.
- Image pushed to ECR, function created.

**Done when:** a test video put in `uploads/` by hand + a console test invoke
produces `results/{job_id}.png` and a `done` job row.

### M4 — SQS + DLQ
- Queue + DLQ, event source mapping with batch size 1.
- Handler parses the SQS event shape; on unrecoverable errors (bad video)
  marks the job `failed` and returns success so it isn't retried; on
  unexpected errors re-raises so SQS retries, then DLQ.

**Done when:** sending a message to the queue processes a job end-to-end, and a
corrupt video ends up `failed` (not retried forever).

### M5 — API job endpoints
- Add `boto3`, the three `/api/jobs` endpoints, and AWS config via env vars
  (`AWS_REGION`, `STACK_BUCKET`, `STACK_QUEUE_URL`, `STACK_JOBS_TABLE`).
- Render gets an IAM user/keys scoped to: presign S3, `SendMessage`, DynamoDB
  read/write on `stack_jobs`.
- S3 bucket CORS allows `PUT` from the frontend origins.

**Done when:** the full flow works with curl: create job → PUT video → start →
poll until `done` → download PNG.

### M6 — Frontend + cutover
- `sharp-skies-fe` `stackVideo` service switches to create → upload → start →
  poll (e.g. every 2s, with a max wait). Processing phase UI stays the same.
- Remove the inline `POST /api/stack` route and `_cv2_pipeline_lock` once the
  frontend no longer calls it.

- Frontend records client-side timings: upload duration, time from start to
  `done`, and result download — so a full end-to-end number exists, not just
  the worker's `elapsed_ms`.

**Done when:** two browsers stacking different videos at the same time both
get correct results, the API stays responsive throughout, and an end-to-end
baseline is recorded for the reference videos (see M8).

### M7 — Separate worker repo
After cutover the stack pipeline is only used by the Lambda, so it moves to
its own repo (e.g. `sharp-skies-stack-worker`), fully separate from the Render
API. Done after M6 so the pipeline never lives in two places while Render
still runs it.

- New repo containing: `handler.py`, the pipeline (`stack_pipeline.py`,
  `video_reader_service.py`, `quality_service.py`, `alignment_service.py`,
  `stack_service.py`, `image_encode.py`), `requirements.txt`, `Dockerfile`,
  `.dockerignore`, README and this spec. Imports change from
  `app.services.*` to the worker's own package.
- Preserve history for the moved files (`git filter-repo` on a clone, or start
  fresh and link back to this repo — either is fine).
- Remove from `sharp-skies-be`: `lambdas/`, the stack pipeline modules in
  `app/services/` (keep `image_encode.py` if `image_io` still uses it).
- Worker repo gets its own deploy (script or GitHub Action: build → push to
  ECR → update function) and its own secrets.
- Infra ownership: the worker repo owns the Lambda, SQS, DLQ and ECR; S3 and
  `stack_jobs` are shared — decide which repo defines them (see open
  questions).

The API ↔ worker contract (SQS message shape, `stack_jobs` fields, S3 key
layout) lives in the worker repo's spec; the API repo links to it. Any
contract change ships worker-first, in a backwards-compatible way, then API.

**Done when:** `sharp-skies-be` has no stack pipeline or Lambda code, the
worker repo builds and deploys on its own, and both reference videos still
produce the same output end-to-end through the API.

### M8 — Faster pipeline (after cutover)
Done after the Lambda path is live, since finding the right speed/quality
balance takes experimentation and shouldn't block the migration.

Reference videos (keep these fixed for every comparison):
- `moon2.mp4` — 22.4MB, 1080x1920, 237 frames. Render: 51s (score 14s,
  align+stack 37s).
- `IMG_2036.MOV` — 5.7MB HEVC, 1080x1920, 316 frames. Render: OOM during
  align+stack.

Candidates, tried one at a time:
- Optical flow at reduced resolution in `align_frames` (try 0.5 and 0.75),
  upsample the flow, warp full-res frames. Then `DISOPTICAL_FLOW_PRESET_FAST`.
- Cheaper scoring: BGR→gray directly, score on a downscaled gray frame.
- Read the video from a file path instead of holding upload bytes in RAM.
- Lambda tuning: 2048 / 3008 / 4096 MB, with OpenCV threading re-enabled.

Output resolution never changes — reduced resolution is only used for the
alignment and scoring *decisions*.

**End-to-end timing table** — fill in at M6 (baseline) and after each change:

| Stage | Source |
|---|---|
| Upload (browser → S3) | Frontend timing |
| Queue wait (`queued_at` → `started_at`) | Job record |
| Download (S3 → `/tmp`) | `phase_ms.download` |
| Scoring | `phase_ms.score` |
| Align + stack | `phase_ms.align_stack` |
| Result upload | `phase_ms.upload` |
| Poll detection lag | Frontend timing |
| Result download | Frontend timing |
| **Total: click → image shown** | Frontend timing |

**Done when:** for each kept change,
- align+stack is faster on both reference videos (target ≥2×),
- the final image's `score_frame` sharpness is within a few percent of the
  baseline, with a side-by-side check at 100% zoom on crater edges,
- ≥90% of selected frames match the full-resolution scoring,
- the end-to-end table is updated.

## Error handling

| Case | Behavior |
|---|---|
| Invalid `top_percent` | 400 at `POST /api/jobs` |
| Start called before upload | 409, job stays `pending_upload` |
| Unreadable/unsupported video (`ValueError` from pipeline) | Job `failed`, message shown to user, no retry |
| Lambda timeout / OOM / unexpected exception | SQS retries once, then DLQ; job left `processing` → API reports `failed` if `updated_at` is older than the Lambda timeout |
| Unknown `job_id` | 404 |

## Limits to enforce

- Max upload size (presigned URL condition) — pick based on M1/M3 memory
  measurements.
- Lambda hard limits: 15 min runtime, 10 GB memory, 10 GB `/tmp`.
- Check the account's Lambda concurrent-execution quota (new accounts can be
  as low as 10) before relying on parallelism.

## Open questions

1. **Infra as code or console?** Console is faster to learn on; AWS SAM or
   CDK makes M2–M5 reproducible. Recommendation: console for M2–M3, then
   capture in SAM before M6.
2. **Does the `oom` branch get merged first?** Its streaming changes reduce
   Lambda memory too, so merging it before M1 means the Lambda starts from the
   leaner pipeline.
3. **Auth:** jobs are currently guessable only by uuid. Fine for v1; needs
   per-user ownership once accounts exist.
4. **Retention:** how many days to keep uploads/results (lifecycle + TTL)?
5. **Polling vs push:** polling is simplest for v1; WebSockets/SSE later if
   needed.
6. **Shared infra after the repo split:** which repo defines the S3 bucket and
   `stack_jobs` table, since both the API and the worker use them?
