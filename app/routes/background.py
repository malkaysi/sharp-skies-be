from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.services.background_service import remove_background
from app.services.image_io import decode_uploaded_image, encode_png

router = APIRouter()


@router.post("/background")
async def background_extraction(
    file: UploadFile = File(...),
    strength: float = Form(1.0),
):
    if not 0.0 <= strength <= 1.0:
        raise HTTPException(status_code=400, detail="strength must be between 0 and 1")

    image = await decode_uploaded_image(file)
    result = remove_background(image, strength=strength)
    return Response(content=encode_png(result), media_type="image/png")
