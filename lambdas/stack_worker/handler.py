import logging
import os
import time
from datetime import datetime, timezone
from decimal import Decimal

import boto3
import cv2

from app.services.stack_pipeline import run_stack

# Lambda's root logger already has a handler; it just defaults to WARNING.
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)

# Match Render for the parity check — threading gets re-tested in M8.
cv2.setNumThreads(1)

BUCKET = os.environ["STACK_BUCKET"]
TABLE = os.environ["STACK_JOBS_TABLE"]

# Created once per container and reused across warm invocations.
s3 = boto3.client("s3")
table = boto3.resource("dynamodb").Table(TABLE)


def handler(event, context):
    """Stack one uploaded video for a job.

    Event: {"job_id": "..."} — filename and top_percent come from the
    job's `stack_jobs` row. Input is uploads/{job_id}{ext}, output is
    results/{job_id}.png.
    """
    job_id = event["job_id"]
    job = table.get_item(Key={"job_id": job_id}).get("Item")
    if job is None:
        # Nothing to update and retrying won't help.
        logger.error("job not found: %s", job_id)
        return {"job_id": job_id, "status": "failed", "error": "job not found"}

    filename = job["filename"]
    top_percent = float(job.get("top_percent", 0))
    ext = os.path.splitext(filename)[1].lower()
    upload_key = f"uploads/{job_id}{ext}"
    result_key = f"results/{job_id}.png"
    local_path = f"/tmp/{job_id}{ext}"

    _update_job(job_id, status="processing", started_at=_now())

    try:
        t0 = time.time()
        s3.download_file(BUCKET, upload_key, local_path)
        download_ms = _ms_since(t0)

        t0 = time.time()
        with open(local_path, "rb") as f:
            data = f.read()
        png, stats = run_stack(data, filename, top_percent)
        stack_ms = _ms_since(t0)
    except ValueError as e:
        # Unreadable/unsupported video — a user error, not worth retrying.
        _update_job(job_id, status="failed", error=str(e), finished_at=_now())
        return {"job_id": job_id, "status": "failed", "error": str(e)}
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

    t0 = time.time()
    s3.put_object(Bucket=BUCKET, Key=result_key, Body=png, ContentType="image/png")
    upload_ms = _ms_since(t0)

    _update_job(
        job_id,
        status="done",
        result_key=result_key,
        finished_at=_now(),
        frames_total=stats["frames_total"],
        frames_selected=stats["frames_selected"],
        top_percent_actual=stats["top_percent"],
        elapsed_ms=stats["elapsed_ms"],
        phase_ms={"download": download_ms, "stack": stack_ms, "upload": upload_ms},
    )
    return {"job_id": job_id, "status": "done", "result_key": result_key, **stats}


def _update_job(job_id: str, **fields) -> None:
    fields["updated_at"] = _now()
    # Placeholders for every name, since some fields (e.g. `status`) are
    # DynamoDB reserved words.
    table.update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in fields),
        ExpressionAttributeNames={f"#{k}": k for k in fields},
        ExpressionAttributeValues={f":{k}": _to_dynamo(v) for k, v in fields.items()},
    )


def _to_dynamo(value):
    # boto3's DynamoDB resource rejects Python floats; numbers must be Decimal.
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamo(v) for k, v in value.items()}
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ms_since(t0: float) -> int:
    return int((time.time() - t0) * 1000)
