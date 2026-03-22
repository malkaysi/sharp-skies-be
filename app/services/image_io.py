from io import BytesIO

from PIL import Image, ImageOps
import cv2
from fastapi import HTTPException, UploadFile
import numpy as np


async def decode_uploaded_image(file: UploadFile) -> np.ndarray:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    image = Image.open(BytesIO(data))
    image = ImageOps.exif_transpose(image)  # Handle EXIF orientation
    image = image.convert("RGB")  # Ensure consistent color mode
    return np.array(image)


def encode_png(image_array: np.ndarray) -> bytes:
    success, buffer = cv2.imencode(
        ".png",
        cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR),
    )

    if not success:
        raise ValueError("Failed to encode image to PNG format")

    return buffer.tobytes()
