import base64
import logging
import resource
import sys
import time

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.services.alignment_service import align_frames
from app.services.image_io import encode_png
from app.services.quality_service import score_frame, select_indices
from app.services.stack_service import stack_frames
from app.services.video_reader_service import (
    extract_frames_by_index,
    score_frames_streaming,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _peak_rss_mb() -> float:
    kb_or_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # ru_maxrss is KB on Linux (Render), bytes on macOS.
    return kb_or_bytes / 1024 if sys.platform != "darwin" else kb_or_bytes / (1024 * 1024)


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

    data = file.file.read()
    filename = file.filename or "uploaded_video"

    t_start = time.time()
    logger.info(
        "stack request: file=%s size=%.1fMB | peak_rss=%.0fMB",
        filename,
        len(data) / 1e6,
        _peak_rss_mb(),
    )

    try:
        scores = score_frames_streaming(data, filename, score_frame)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    frames_total = len(scores)
    logger.info(
        "scored %d frames | peak_rss=%.0fMB", frames_total, _peak_rss_mb()
    )

    selected_indices = select_indices(scores, top_percent)
    selected_scores = [scores[i] for i in selected_indices]
    del scores

    selected_frames = extract_frames_by_index(data, filename, selected_indices)
    frame_h, frame_w = selected_frames[0].shape[:2]
    est_selected_mb = len(selected_frames) * frame_h * frame_w * 3 / 1e6
    logger.info(
        "extracted %d/%d selected frames, resolution=%dx%d, "
        "est_selected_size=%.0fMB | peak_rss=%.0fMB",
        len(selected_frames),
        frames_total,
        frame_w,
        frame_h,
        est_selected_mb,
        _peak_rss_mb(),
    )

    reference = selected_frames[0]
    aligned_frames = align_frames(selected_frames, reference)
    result = stack_frames(aligned_frames, selected_scores)
    logger.info("aligned + stacked | peak_rss=%.0fMB", _peak_rss_mb())

    elapsed_ms = int((time.time() - t_start) * 1000)
    image_b64 = base64.b64encode(encode_png(result)).decode("utf-8")
    logger.info(
        "stack request done in %dms | peak_rss=%.0fMB", elapsed_ms, _peak_rss_mb()
    )

    return JSONResponse(
        {
            "image": image_b64,
            "frames_total": frames_total,
            "frames_selected": len(selected_frames),
            "top_percent": round(len(selected_frames) / frames_total * 100, 1),
            "elapsed_ms": elapsed_ms,
        }
    )
