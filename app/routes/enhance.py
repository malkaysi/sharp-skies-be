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


DEFAULT_LAYERS = '[{"strength":1.0,"denoise":0.0},{"strength":1.0,"denoise":0.0},{"strength":1.0,"denoise":0.0},{"strength":1.0,"denoise":0.0},{"strength":1.0,"denoise":0.0},{"strength":1.0,"denoise":0.0}]'


@router.post("/enhance/wavelet")
async def enhance_image_wavelet(
    file: UploadFile = File(...),
    layers: str = Form(DEFAULT_LAYERS),
):
    try:
        parsed = json.loads(layers)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="layers must be a JSON array")

    if not isinstance(parsed, list) or len(parsed) < 1 or len(parsed) > 8:
        raise HTTPException(status_code=400, detail="layers must have 1-8 entries")

    for i, layer in enumerate(parsed):
        if not isinstance(layer, dict):
            raise HTTPException(
                status_code=400, detail=f"layer {i + 1} must be an object"
            )
        if layer.get("strength", 1.0) < 0:
            raise HTTPException(
                status_code=400, detail=f"layer {i + 1} strength must be >= 0"
            )
        if layer.get("denoise", 0.0) < 0:
            raise HTTPException(
                status_code=400, detail=f"layer {i + 1} denoise must be >= 0"
            )

    image_array = await decode_uploaded_image(file)
    result = enhance_wavelets(image_array=image_array, layers=parsed)
    return Response(content=encode_png(result), media_type="image/png")
