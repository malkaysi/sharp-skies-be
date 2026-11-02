# Stack Worker (Lambda)

Runs the video-stacking pipeline (`app/services/video_reader_service.py`,
`quality_service.py`, `alignment_service.py`, `stack_service.py`,
`image_io.py`) as a container-image Lambda function, instead of inline in
the FastAPI `/stack` route.

Status: not yet built. First goal is a local smoke test — no AWS resources
created yet.

## Why this exists

The `/stack` route in the main API does 30s-2min of CPU/memory-heavy video
processing per request. That doesn't fit a synchronous web request well
(see the OOM/segfault history on that route). This Lambda is the eventual
target for that work: triggered by SQS, reads the uploaded video from S3,
runs the same pipeline, writes the result back to S3.

## Status of the pieces

- [x] Hello-world handler, Dockerfile, tested locally via the Lambda Runtime
      Interface Emulator (`docker run -p 9000:8080` + curl invoke) — confirmed
      the AWS Lambda base image, our handler shape, and a real invocation
      round-trip all work
- [ ] Handler that runs the actual pipeline against a local test file
- [ ] S3 bucket + IAM role
- [ ] Deployed to Lambda, manually invoked against a real test video
- [ ] SQS wired in front of it
- [ ] `/stack` route in `app/routes/stack.py` updated to enqueue instead of
      processing inline
