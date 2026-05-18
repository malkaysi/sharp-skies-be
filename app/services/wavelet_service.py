import cv2
import numpy as np


def wavelet_decompose(channel: np.ndarray, num_layers: int) -> list[np.ndarray]:
    layers = []
    current = channel.astype(np.float32)
    for i in range(num_layers):
        sigma = 2**i
        blurred = cv2.GaussianBlur(current, (0, 0), sigmaX=sigma)
        detail = current - blurred
        layers.append(detail)
        current = blurred
    layers.append(current)
    return layers


def wavelet_reconstruct(layers: list[np.ndarray]) -> np.ndarray:
    return sum(layers)


def enhance_wavelets(
    image_array: np.ndarray,
    layers: list[dict],
) -> np.ndarray:
    """
    layers: list of dicts with keys:
      - strength: float  (>1 sharpen, <1 soften, 1.0 unchanged)
      - denoise: float   (zero out detail values below this, 0.0 = off)
    """
    num_layers = len(layers)

    lab = cv2.cvtColor(image_array, cv2.COLOR_RGB2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)

    detail_layers = wavelet_decompose(l_channel, num_layers)

    for i in range(num_layers):
        strength = layers[i].get("strength", 1.0)
        denoise = layers[i].get("denoise", 0.0)

        if denoise > 0:
            detail_layers[i][np.abs(detail_layers[i]) < denoise] = 0

        detail_layers[i] = detail_layers[i] * strength

    result_l = wavelet_reconstruct(detail_layers)
    result_l = np.clip(result_l, 0, 255).astype(np.uint8)

    result_lab = cv2.merge((result_l, a_channel, b_channel))
    return cv2.cvtColor(result_lab, cv2.COLOR_LAB2RGB)
