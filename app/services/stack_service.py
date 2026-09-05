from collections.abc import Iterable

import numpy as np


def stack_frames(
    aligned_frames: Iterable[tuple[int, np.ndarray]], scores_by_index: dict[int, float]
) -> np.ndarray:
    indices = list(scores_by_index.keys())
    score_arr = np.array([scores_by_index[i] for i in indices], dtype=np.float32)
    score_arr -= score_arr.min()
    total = score_arr.sum()
    if total == 0:
        weight_by_index = {i: 1.0 / len(indices) for i in indices}
    else:
        weight_by_index = dict(zip(indices, score_arr / total))

    # aligned_frames may be a generator, so accumulate as we go rather than
    # indexing into it up front — avoids ever holding a full second list of
    # warped frames alongside the originals. Mutate in place (`*=`/`+=`)
    # rather than `weight * frame` / `stack + contribution`, which would
    # each allocate a brand-new full-res array on every iteration.
    stack = None
    for idx, frame in aligned_frames:
        weighted = frame.astype(np.float32)
        weighted *= weight_by_index[idx]
        if stack is None:
            stack = weighted
        else:
            stack += weighted

    return np.clip(stack, 0, 255).astype(np.uint8)
