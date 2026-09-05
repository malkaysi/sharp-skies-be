from collections.abc import Iterator

import cv2
import numpy as np


def align_frames(
    frames: list[np.ndarray], reference: np.ndarray
) -> Iterator[np.ndarray]:
    """Yields each frame warped onto `reference`, one at a time.

    A generator rather than a list so the caller (stack_frames) can accumulate
    each warped frame immediately instead of holding a second full-res copy
    of every frame alongside the originals.
    """
    ref_gray = cv2.cvtColor(reference, cv2.COLOR_RGB2GRAY)
    h, w = ref_gray.shape

    x_coords, y_coords = np.meshgrid(
        np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32)
    )

    dis = cv2.DISOpticalFlow.create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)

    for frame in frames:
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        flow = dis.calc(ref_gray, frame_gray, None)
        map_x = x_coords + flow[..., 0]
        map_y = y_coords + flow[..., 1]
        yield cv2.remap(
            frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
        )
