from io import BytesIO

from fastapi import FastAPI, File, UploadFile
from PIL import Image
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

    # Convert to Numpy array to check dimensions
    image_array = np.array(image)

    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "image_mode": image.mode,
        "image_size": list(image.size),
        "image_array_shape": list(image_array.shape),
        "dtype": str(image_array.dtype),
    }
