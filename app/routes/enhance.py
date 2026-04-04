import json

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from app.services.enhance_service import enhance_luminance
from app.services.image_io import decode_uploaded_image, encode_png
from app.services.wavelet_service import enhance_wavelets


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


@router.post("/enhance/wavelet")
async def enhance_image_wavelet(
    file: UploadFile = File(...),
    layer_strengths: str = Form("[1.0, 1.0, 1.0, 1.0, 1.0, 1.0]"),
    denoise_threshold: float = Form(0.0),
):
    # Parse the JSON array of layer strengths
    try:
        strengths = json.loads(layer_strengths)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(
            status_code=400, detail="layer_strengths must be a JSON array of numbers"
        )

    if not isinstance(strengths, list) or not all(
        isinstance(s, (int, float)) for s in strengths
    ):
        raise HTTPException(
            status_code=400, detail="layer_strengths must be an array of numbers"
        )
    if len(strengths) < 1 or len(strengths) > 8:
        raise HTTPException(
            status_code=400, detail="layer_strengths must have 1-8 layers"
        )
    if any(s < 0 for s in strengths):
        raise HTTPException(status_code=400, detail="layer strengths must be >= 0")
    if denoise_threshold < 0:
        raise HTTPException(status_code=400, detail="denoise_threshold must be >= 0")

    image_array = await decode_uploaded_image(file)

    result = enhance_wavelets(
        image_array=image_array,
        layer_strengths=strengths,
        denoise_threshold=denoise_threshold,
    )

    output = encode_png(result)
    return Response(content=output, media_type="image/png")
