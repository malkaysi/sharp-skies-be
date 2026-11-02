import logging
import resource
import sys
import time

from app.services.alignment_service import align_frames
from app.services.image_encode import encode_png
from app.services.quality_service import score_frame, select_indices
from app.services.stack_service import stack_frames
from app.services.video_reader_service import (
    extract_frames_by_index,
    extract_frames_by_index_streaming,
    score_frames_streaming,
)

logger = logging.getLogger(__name__)


def peak_rss_mb() -> float:
    kb_or_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # ru_maxrss is KB on Linux (Render/Lambda), bytes on macOS.
    return kb_or_bytes / 1024 if sys.platform != "darwin" else kb_or_bytes / (1024 * 1024)


def run_stack(data: bytes, filename: str, top_percent: float = 0.0) -> tuple[bytes, dict]:
    """Scores, selects, aligns and stacks a video's frames.

    Shared by the FastAPI `/stack` route and the Lambda stack worker, so both
    run the exact same pipeline. Raises ValueError if no frames can be read.
    Returns the stacked PNG bytes and the stats the frontend displays.
    """
    t_start = time.time()
    logger.info(
        "stack start: file=%s size=%.1fMB | peak_rss=%.0fMB",
        filename,
        len(data) / 1e6,
        peak_rss_mb(),
    )

    scores = score_frames_streaming(data, filename, score_frame)
    frames_total = len(scores)
    logger.info("scored %d frames | peak_rss=%.0fMB", frames_total, peak_rss_mb())

    selected_indices = select_indices(scores, top_percent)
    scores_by_index = {i: scores[i] for i in selected_indices}
    del scores

    # Only the reference frame is decoded up front (it must exist before
    # any other frame can be aligned to it) — everything else streams
    # through align_frames -> stack_frames one at a time, so peak memory
    # here is ~2 full-res frames + the running accumulator, not
    # frames_selected of them.
    reference_index = selected_indices[0]
    reference = extract_frames_by_index(data, filename, [reference_index])[0]
    frame_h, frame_w = reference.shape[:2]
    est_unstreamed_mb = len(selected_indices) * frame_h * frame_w * 3 / 1e6
    logger.info(
        "selected %d/%d frames, resolution=%dx%d, "
        "would-be-buffered-size=%.0fMB | peak_rss=%.0fMB",
        len(selected_indices),
        frames_total,
        frame_w,
        frame_h,
        est_unstreamed_mb,
        peak_rss_mb(),
    )

    frame_stream = extract_frames_by_index_streaming(data, filename, selected_indices)
    aligned_stream = align_frames(frame_stream, reference)
    result = stack_frames(aligned_stream, scores_by_index)
    logger.info("aligned + stacked | peak_rss=%.0fMB", peak_rss_mb())

    elapsed_ms = int((time.time() - t_start) * 1000)
    png = encode_png(result)
    logger.info("stack done in %dms | peak_rss=%.0fMB", elapsed_ms, peak_rss_mb())

    stats = {
        "frames_total": frames_total,
        "frames_selected": len(selected_indices),
        "top_percent": round(len(selected_indices) / frames_total * 100, 1),
        "elapsed_ms": elapsed_ms,
    }
    return png, stats
