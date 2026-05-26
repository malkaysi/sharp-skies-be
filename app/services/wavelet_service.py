import cv2
import numpy as np


def wavelet_decompose(channel: np.ndarray, num_layers: int) -> list[np.ndarray]:
    layers = []
    current = channel.astype(np.float32)

    for i in range(num_layers):
        # Sigma doubles each pass: 1, 2, 4, 8, 16, 32 px — larger = broader structures
        sigma = 2**i
        blurred = cv2.GaussianBlur(current, (0, 0), sigmaX=sigma)

        # Detail = what blurring removed (edges, texture, noise at this scale)
        detail = current - blurred
        layers.append(detail)

        # Next pass works on the blurred version so each layer isolates a coarser scale
        current = blurred

    # Final residual is the low-frequency base (smooth background, gradients)
    layers.append(current)
    return layers


def wavelet_reconstruct(layers: list[np.ndarray]) -> np.ndarray:
    # Summing all detail layers + residual perfectly reconstructs the original
    return sum(layers)


def soft_threshold(detail: np.ndarray, threshold: float) -> np.ndarray:
    # Shrinks values toward zero by the threshold amount rather than hard-cutting them
    # Avoids ringing artifacts at star edges that hard thresholding causes
    return np.sign(detail) * np.maximum(0.0, np.abs(detail) - threshold)


def enhance_wavelets(
    image_array: np.ndarray,
    layers: list[dict],
) -> np.ndarray:
    """
    layers: list of dicts with keys:
      - strength: float  (>1 sharpen, <1 soften, 1.0 unchanged)
      - denoise: float   (soft threshold on detail, 0.0 = off)
      - clip: float      (max detail amplitude after strength, 0.0 = off)
      - blend: float     (0.0 = original detail, 1.0 = fully processed, default 1.0)
    """
    num_layers = len(layers)

    # Convert to LAB and work on luminance only — sharpening color channels causes fringing
    lab = cv2.cvtColor(image_array, cv2.COLOR_RGB2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)

    # Split luminance into num_layers detail layers + 1 residual
    detail_layers = wavelet_decompose(l_channel, num_layers)

    for i in range(num_layers):
        strength = layers[i].get("strength", 1.0)
        denoise  = layers[i].get("denoise", 0.0)
        clip     = layers[i].get("clip", 0.0)
        blend    = layers[i].get("blend", 1.0)

        # Save original before processing so we can blend back at the end
        original_detail = detail_layers[i].copy()

        # Step 1: suppress noise before amplifying — denoising after strength
        # would amplify noise first then threshold it, producing worse results
        if denoise > 0:
            detail_layers[i] = soft_threshold(detail_layers[i], denoise)

        # Step 2: amplify or suppress detail at this frequency scale
        detail_layers[i] = detail_layers[i] * strength

        # Step 3: cap maximum detail amplitude to prevent halos around bright stars
        if clip > 0:
            detail_layers[i] = np.clip(detail_layers[i], -clip, clip)

        # Step 4: blend between original and processed detail
        # blend=1.0 uses processed result, blend=0.0 leaves this layer untouched
        detail_layers[i] = original_detail * (1 - blend) + detail_layers[i] * blend

    # Reconstruct luminance from modified detail layers + residual
    result_l = wavelet_reconstruct(detail_layers)
    result_l = np.clip(result_l, 0, 255).astype(np.uint8)

    # Merge back with untouched color channels and convert to RGB
    result_lab = cv2.merge((result_l, a_channel, b_channel))
    return cv2.cvtColor(result_lab, cv2.COLOR_LAB2RGB)
