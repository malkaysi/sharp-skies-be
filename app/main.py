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

    # Apply Gaussian blur (your first "processing")
    blurred = cv2.GaussianBlur(image_array, (0, 0), sigmaX=2)
    success, buffer = cv2.imencode(".png", blurred)

    if not success:
        return {"error": "Failed to process image"}

    return Response(content=buffer.tobytes(), media_type="image/png")
