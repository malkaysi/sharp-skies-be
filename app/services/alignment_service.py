from collections.abc import Iterable, Iterator

import cv2
import numpy as np


def align_frames(
    frames: Iterable[tuple[int, np.ndarray]], reference: np.ndarray
) -> Iterator[tuple[int, np.ndarray]]:
    """Yields each (index, frame) warped onto `reference`, one at a time.

    Both input and output are streamed, carrying the original frame index
    through so the caller can still look up its score/weight after
    streaming — without ever holding more than the current frame (plus the
    reference) in memory, regardless of how many frames were selected.
    """
    ref_gray = cv2.cvtColor(reference, cv2.COLOR_RGB2GRAY)
    h, w = ref_gray.shape

    x_coords, y_coords = np.meshgrid(
        np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32)
    )

    dis = cv2.DISOpticalFlow.create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)

    for idx, frame in frames:
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        flow = dis.calc(ref_gray, frame_gray, None)
        map_x = x_coords + flow[..., 0]
        map_y = y_coords + flow[..., 1]
        warped = cv2.remap(
            frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
        )
        yield idx, warped
