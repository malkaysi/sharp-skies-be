import cv2
import numpy as np


def wavelet_decompose(channel: np.ndarray, num_layers: int) -> list[np.ndarray]:
    """Decompose a channel into wavelet detail layers + residual.

    Each layer captures detail at a progressively coarser scale.
    The last element is the low-frequency residual (base).
    """
    layers = []
    current = channel.astype(np.float32)

    for i in range(num_layers):
        # Each layer uses a sigma that doubles: 1, 2, 4, 8, 16, 32
        sigma = 2**i
        blurred = cv2.GaussianBlur(current, (0, 0), sigmaX=sigma)
        detail = current - blurred
        layers.append(detail)
        current = blurred

    # Final element is the residual (smooth base)
    layers.append(current)
    return layers


def wavelet_reconstruct(layers: list[np.ndarray]) -> np.ndarray:
    """Sum all detail layers + residual back into a single channel."""
    return sum(layers)


def enhance_wavelets(
    image_array: np.ndarray,
    layer_strengths: list[float],
    denoise_threshold: float = 0.0,
) -> np.ndarray:
    """Sharpen an image using multi-scale wavelet decomposition on luminance.

    Args:
        image_array: RGB uint8 numpy array.
        layer_strengths: Multiplier per detail layer, e.g. [1.5, 1.3, 1.0, 0.8, 0.5, 0.3].
                         Values > 1 sharpen, < 1 soften, 1.0 leaves unchanged.
                         Length determines number of wavelet layers.
        denoise_threshold: Detail values below this in the finest layer (index 0)
                           are zeroed out to suppress noise.
    """
    num_layers = len(layer_strengths)

    # RGB -> LAB, work on luminance only
    lab = cv2.cvtColor(image_array, cv2.COLOR_RGB2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)

    # Decompose luminance into frequency layers
    layers = wavelet_decompose(l_channel, num_layers)

    # Apply per-layer sharpening strengths to detail layers (not the residual)
    for i in range(num_layers):
        # Denoise the finest layer
        if i == 0 and denoise_threshold > 0:
            layers[i][np.abs(layers[i]) < denoise_threshold] = 0

        layers[i] = layers[i] * layer_strengths[i]

    # Reconstruct and clip
    result_l = wavelet_reconstruct(layers)
    result_l = np.clip(result_l, 0, 255).astype(np.uint8)

    result_lab = cv2.merge((result_l, a_channel, b_channel))
    return cv2.cvtColor(result_lab, cv2.COLOR_LAB2RGB)
