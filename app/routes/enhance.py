from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from app.services.enhance_service import enhance_luminance
from app.services.image_io import decode_uploaded_image, encode_png


router = APIRouter()


@router.post("/enhance")
async def enhance_image(
    file: UploadFile = File(...),
    sigma: float = Form(1.2),
    threshold: float = Form(8.0),
    amount: float = Form(0.8),
    blend: float = Form(0.5),
):
    if sigma <= 0:
        raise HTTPException(status_code=400, detail="sigma must be greater than 0")
    if threshold < 0:
        raise HTTPException(status_code=400, detail="threshold must be 0 or greater")
    if amount < 0:
        raise HTTPException(status_code=400, detail="amount must be 0 or greater")
    if not 0 <= blend <= 1:
        raise HTTPException(status_code=400, detail="blend must be between 0 and 1")

    image_array = await decode_uploaded_image(file)

    result = enhance_luminance(
        image_array=image_array,
        sigma=sigma,
        threshold=threshold,
        amount=amount,
        blend=blend,
    )

    output = encode_png(result)

    return Response(content=output, media_type="image/png")
