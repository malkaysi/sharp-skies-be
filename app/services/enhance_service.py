import cv2
import numpy as np

# Sigma - Adjusts the amount of blur (and thus sharpening)
# A smaller sigma targets finer detail.
# A larger sigma creates a broader blur and therefore broader sharpening.

# Threshold - Removes small details (noise)
# A lower threshold will retain more details, while a higher threshold will remove more details.

# Amount - Adjusts the strength of sharpening (0.5 is moderate)
# A higher amount will create a more pronounced sharpening effect, while a lower amount will create a

# Blend - Blends the sharpened image back with the original to reduce overall sharpening effect
# A higher blend will create a more pronounced sharpening effect, while a lower blend will keep more of the original image.


def enhance_luminance(
    image_array: np.ndarray, sigma: float, threshold: float, amount: float, blend: float
) -> np.ndarray:

    # Convert RGB -> LAB
    lab = cv2.cvtColor(image_array, cv2.COLOR_RGB2LAB)

    # Split LAB channels
    l_channel, a_channel, b_channel = cv2.split(lab)

    # Convert L channel to float for safer math
    l_float = l_channel.astype(np.float32)

    # Blur only the luminance channel
    # Create a blurred version
    blurred_l = cv2.GaussianBlur(l_float, (0, 0), sigmaX=sigma)

    # Extract luminance detail
    detail = l_float - blurred_l
    detail[np.abs(detail) < threshold] = 0

    # Unsharp mask formula
    sharpened_l = l_float + amount * detail

    # Blend back with the original to reduce overall sharpening effect
    result_l = (l_float * (1 - blend)) + (sharpened_l * blend)

    # Keep values in valid image range
    result_l = np.clip(result_l, 0, 255).astype(np.uint8)

    # Merge sharpened L back with original color channels
    result_lab = cv2.merge((result_l, a_channel, b_channel))

    # Convert LAB -> RGB
    enhanced_rgb = cv2.cvtColor(result_lab, cv2.COLOR_LAB2RGB)
    return enhanced_rgb
