import base64
import logging
import threading

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.services.stack_pipeline import peak_rss_mb, run_stack

router = APIRouter()
logger = logging.getLogger(__name__)

# `stack_video` runs in a worker thread (see docstring below), so two
# requests can now genuinely run their CV2 pipelines at the same time in this
# process — something that was never possible before. OpenCV/FFmpeg aren't
# guaranteed safe under that kind of concurrent access and can crash natively
# (segfault) rather than raise a catchable exception. This process only has
# one CPU to give either request anyway, so there's no throughput cost to
# strictly serializing the CV2-heavy work.
_cv2_pipeline_lock = threading.Lock()


@router.post("/stack")
def stack_video(
    file: UploadFile = File(...),  # noqa: B008
    top_percent: float = Form(0.0),
):
    """Plain `def`, not `async def`: this does minutes of blocking CPU work
    (OpenCV/NumPy), and none of it awaits anything. An async route would run
    that on the single event loop thread, freezing the whole server —
    including Render's health check ping — until it finished. FastAPI runs
    sync routes in a worker thread instead, keeping the event loop free.
    """
    if top_percent < 0.0 or top_percent > 100.0:
        raise HTTPException(
            status_code=400, detail="top_percent must be between 0 and 100"
        )

    filename = file.filename or "uploaded_video"
    logger.info(
        "stack request received: file=%s | peak_rss=%.0fMB", filename, peak_rss_mb()
    )

    with _cv2_pipeline_lock:
        # Read the upload only once it's this request's turn — a request
        # queued behind another shouldn't hold its full raw video in memory
        # while it waits, on top of whatever the active request is using.
        data = file.file.read()
        try:
            png, stats = run_stack(data, filename, top_percent)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return JSONResponse({"image": base64.b64encode(png).decode("utf-8"), **stats})
