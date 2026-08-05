import cv2
import numpy as np


def align_frames(frames: list[np.ndarray], reference: np.ndarray) -> list[np.ndarray]:
    ref_gray = cv2.cvtColor(reference, cv2.COLOR_RGB2GRAY)
    h, w = ref_gray.shape

    x_coords, y_coords = np.meshgrid(
        np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32)
    )

    dis = cv2.DISOpticalFlow.create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    aligned = []

    for frame in frames:
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        flow = dis.calc(ref_gray, frame_gray, None)
        map_x = x_coords + flow[..., 0]
        map_y = y_coords + flow[..., 1]
        warped = cv2.remap(
            frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
        )
        aligned.append(warped)

    return aligned
