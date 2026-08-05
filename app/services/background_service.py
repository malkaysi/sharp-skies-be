import cv2
import numpy as np


def remove_background(image: np.ndarray, strength: float = 1.0) -> np.ndarray:
    h, w = image.shape[:2]
    img_f = image.astype(np.float32)

    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    moon_mask = np.zeros((h, w), dtype=np.uint8)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        cv2.drawContours(moon_mask, [largest], -1, 255, thickness=cv2.FILLED)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (51, 51))
    moon_mask = cv2.dilate(moon_mask, kernel)

    inpainted = cv2.inpaint(image, moon_mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)

    sigma = min(h, w) // 6
    background = cv2.GaussianBlur(inpainted.astype(np.float32), (0, 0), sigma)

    result = img_f - strength * background
    return np.clip(result, 0, 255).astype(np.uint8)
