import cv2
import numpy as np


def encode_png(image_array: np.ndarray) -> bytes:
    success, buffer = cv2.imencode(
        ".png",
        cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR),
    )

    if not success:
        raise ValueError("Failed to encode image to PNG format")

    return buffer.tobytes()
