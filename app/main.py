from io import BytesIO

import cv2
import numpy as np
from fastapi import FastAPI, File, Response, UploadFile
from PIL import Image, ImageOps

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

    # Force RGB so color handling is predictable
    image = image.convert("RGB")

    # Convert to NumPy array so we can process pixel values
    image_array = np.array(image)

    # Convert RGB -> LAB
    lab = cv2.cvtColor(image_array, cv2.COLOR_RGB2LAB)

    # Split LAB channels
    l_channel, a_channel, b_channel = cv2.split(lab)

    # Convert L channel to float for safer math
    l_float = l_channel.astype(np.float32)

    # Blur only the luminance channel
    # Create a blurred version
    # Change SigmaX to adjust the amount of blur (and thus sharpening)
    # A smaller sigma targets finer detail.
    # A larger sigma creates a broader blur and therefore broader sharpening.
    blurred_l = cv2.GaussianBlur(l_float, (0, 0), sigmaX=1.0)

    # Extract luminance detail
    detail = l_float - blurred_l

    # Threshold to remove small details (noise)
    # A lower threshold will retain more details, while a higher threshold will remove more details.
    threshold = 8.0
    detail[np.abs(detail) < threshold] = 0

    # Unsharp mask formula
    # Change amount to adjust the strength of sharpening (0.5 is moderate)
    # A higher amount will create a more pronounced sharpening effect, while a lower amount will create a subtler effect.
    amount = 0.5
    sharpened_l = l_float + amount * detail

    # Blend back with the original to reduce overall sharpening effect
    # A higher blend will create a more pronounced sharpening effect,
    # while a lower blend will keep more of the original image.
    blend = 0.5
    result_l = (l_float * (1 - blend)) + (sharpened_l * blend)

    # Keep values in valid image range
    result_l = np.clip(result_l, 0, 255).astype(np.uint8)

    # Merge sharpened L back with original color channels
    result_lab = cv2.merge((result_l, a_channel, b_channel))

    # Convert LAB -> RGB
    result_rgb = cv2.cvtColor(result_lab, cv2.COLOR_LAB2RGB)

    success, buffer = cv2.imencode(".png", cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR))

    if not success:
        return {"error": "Failed to process image"}

    return Response(content=buffer.tobytes(), media_type="image/png")
