from collections.abc import Iterable

import numpy as np


def stack_frames(aligned_frames: Iterable[np.ndarray], scores: list[float]) -> np.ndarray:
    score_arr = np.array(scores, dtype=np.float64)
    score_arr -= score_arr.min()
    total = score_arr.sum()
    if total == 0:
        weights = np.ones(len(scores)) / len(scores)
    else:
        weights = score_arr / total

    # aligned_frames may be a generator, so accumulate as we go rather than
    # indexing into it up front — avoids ever holding a full second list of
    # warped frames alongside the originals.
    stack = None
    for frame, w in zip(aligned_frames, weights):
        contribution = w * frame.astype(np.float64)
        stack = contribution if stack is None else stack + contribution

    return np.clip(stack, 0, 255).astype(np.uint8)
