import numpy as np


def stack_frames(aligned_frames: list[np.ndarray], scores: list[float]) -> np.ndarray:
    score_arr = np.array(scores, dtype=np.float64)
    score_arr -= score_arr.min()
    total = score_arr.sum()
    if total == 0:
        weights = np.ones(len(scores)) / len(scores)
    else:
        weights = score_arr / total

    stack = np.zeros_like(aligned_frames[0], dtype=np.float64)
    for frame, w in zip(aligned_frames, weights):
        stack += w * frame.astype(np.float64)

    return np.clip(stack, 0, 255).astype(np.uint8)
