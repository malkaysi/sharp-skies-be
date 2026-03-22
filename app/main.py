from io import BytesIO

import cv2
from fastapi import FastAPI, File, Response, UploadFile
from PIL import Image, ImageOps
import numpy as np

app = FastAPI()


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/upload-test")
async def upload_test(file: UploadFile = File(...)):
    data = await file.read()

    # Open in Pillow to get image properties
    image = Image.open(BytesIO(data))
    image = ImageOps.exif_transpose(image)

    # Convert to Numpy array to check dimensions
    image_array = np.array(image)

    # Convert to float so math is safer
    arr_float = image_array.astype(np.float32)

    # Create a blurred version
    # Change SigmaX to adjust the amount of blur (and thus sharpening)
    # A smaller sigma will create a sharper image, while a larger sigma will create a softer image.
    blurred = cv2.GaussianBlur(arr_float, (0, 0), sigmaX=1.0)

    detail = arr_float - blurred

    # Threshold to remove small details (noise)
    # A lower threshold will retain more details, while a higher threshold will remove more details.
    threshold = 8.0
    detail[np.abs(detail) < threshold] = 0

    # Unsharp mask formula
    # Change amount to adjust the strength of sharpening (0.5 is moderate)
    # A higher amount will create a more pronounced sharpening effect, while a lower amount will create a subtler effect.
    amount = 0.5
    sharpened = arr_float + amount * detail

    # Blend back with the original to reduce overall sharpening effect
    # A higher blend will create a more pronounced sharpening effect,
    # while a lower blend will keep more of the original image.
    blend = 0.5
    result = (arr_float * (1 - blend)) + (sharpened * blend)

    # Keep values in valid image range
    result = np.clip(result, 0, 255).astype(np.uint8)

    success, buffer = cv2.imencode(".png", result)

    if not success:
        return {"error": "Failed to process image"}

    return Response(content=buffer.tobytes(), media_type="image/png")
