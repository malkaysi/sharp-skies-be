from io import BytesIO

from PIL import Image, ImageOps
from fastapi import HTTPException, UploadFile
import numpy as np

from app.services.image_encode import encode_png  # noqa: F401 — re-exported for routes


async def decode_uploaded_image(file: UploadFile) -> np.ndarray:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    image = Image.open(BytesIO(data))
    image = ImageOps.exif_transpose(image)  # Handle EXIF orientation
    image = image.convert("RGB")  # Ensure consistent color mode
    return np.array(image)
