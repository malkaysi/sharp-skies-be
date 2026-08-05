from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from app.services.image_io import encode_png
from app.services.video_reader_service import extract_frames


router = APIRouter()


@router.post("/stack")
async def stack_video(
    file: UploadFile = File(...),
    top_percent: float = Form(0.0),
):
    if top_percent < 0.0 or top_percent > 100.0:
        raise HTTPException(
            status_code=400, detail="top_percent must be between 0 and 100"
        )

    data = await file.read()
    filename = file.filename or "uploaded_video"

    try:
        frames = extract_frames(data, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if len(frames) == 0:
        raise HTTPException(
            status_code=400, detail="No frames extracted from the video"
        )

    scores = [score_frame(f) for f in frames]
    selected_frames, selected_scores = rank_and_select_frames(
        frames, scores, top_percent
    )
    reference = selected_frames[0]
    # Won't the reference potentially be bad if we're choosing the first frame?
    aligned_frames = align_frames(selected_frames, reference)
    result = stack_frames(aligned_frames, selected_scores)

    return Response(content=encode_png(result), media_type="image/png")
