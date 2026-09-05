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

    # Reused across every frame instead of allocating fresh per iteration.
    # Safe because each yielded `warped` is fully consumed (copied out) by
    # the caller before the generator resumes to overwrite it.
    frame_gray_buf = np.empty((h, w), dtype=np.uint8)
    flow_buf = np.empty((h, w, 2), dtype=np.float32)
    map_x_buf = np.empty((h, w), dtype=np.float32)
    map_y_buf = np.empty((h, w), dtype=np.float32)
    warped_buf = np.empty_like(reference)

    for idx, frame in frames:
        cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY, dst=frame_gray_buf)
        dis.calc(ref_gray, frame_gray_buf, flow_buf)
        np.add(x_coords, flow_buf[..., 0], out=map_x_buf)
        np.add(y_coords, flow_buf[..., 1], out=map_y_buf)
        warped = cv2.remap(
            frame,
            map_x_buf,
            map_y_buf,
            cv2.INTER_LINEAR,
            dst=warped_buf,
            borderMode=cv2.BORDER_REFLECT,
        )
        yield idx, warped
