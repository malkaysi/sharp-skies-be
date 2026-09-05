import base64
import time

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.services.alignment_service import align_frames
from app.services.image_io import encode_png
from app.services.quality_service import rank_and_select, score_frame
from app.services.stack_service import stack_frames
from app.services.video_reader_service import extract_frames

router = APIRouter()


@router.post("/stack")
async def stack_video(
    file: UploadFile = File(...),  # noqa: B008
    top_percent: float = Form(0.0),
):
    if top_percent < 0.0 or top_percent > 100.0:
        raise HTTPException(
            status_code=400, detail="top_percent must be between 0 and 100"
        )

    data = await file.read()
    filename = file.filename or "uploaded_video"

    t_start = time.time()

    try:
        frames = extract_frames(data, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    frames_total = len(frames)
    if frames_total == 0:
        raise HTTPException(
            status_code=400, detail="No frames extracted from the video"
        )

    scores = [score_frame(f) for f in frames]
    selected_frames, selected_scores = rank_and_select(frames, scores, top_percent)
    del frames, scores  # release unselected full-res frames before alignment

    reference = selected_frames[0]
    aligned_frames = align_frames(selected_frames, reference)
    result = stack_frames(aligned_frames, selected_scores)

    elapsed_ms = int((time.time() - t_start) * 1000)
    image_b64 = base64.b64encode(encode_png(result)).decode("utf-8")

    return JSONResponse(
        {
            "image": image_b64,
            "frames_total": frames_total,
            "frames_selected": len(selected_frames),
            "top_percent": round(len(selected_frames) / frames_total * 100, 1),
            "elapsed_ms": elapsed_ms,
        }
    )
