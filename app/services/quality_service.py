import cv2
import numpy as np


def score_frame(frame: np.ndarray) -> float:
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY).astype(np.float64)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F).var()
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    tenengrad = float(np.mean(sobel_x**2 + sobel_y**2))
    # Could we eventually use machine learning or something else to make this better?
    return 0.6 * laplacian + 0.4 * tenengrad


def rank_and_select(
    frames: list[np.ndarray],
    scores: list[float],
    top_percent: float = 0.0,
) -> tuple[list[np.ndarray], list[float]]:
    paired = sorted(zip(scores, frames), key=lambda x: x[0], reverse=True)
    sorted_scores = [p[0] for p in paired]
    sorted_frames = [p[1] for p in paired]

    n = len(sorted_frames)

    if top_percent > 0.0:
        k = max(1, int(round(n * top_percent / 100.0)))
    else:
        k = _auto_select_count(sorted_scores)

    return sorted_frames[:k], sorted_scores[:k]


def _auto_select_count(sorted_scores: list[float]) -> int:
    n = len(sorted_scores)
    min_k = max(1, int(n * 0.20))
    max_k = max(min_k + 1, int(n * 0.80))

    if n <= 2:
        return n

    arr = np.array(sorted_scores)
    diffs = arr[:-1] - arr[1:]
    elbow = int(np.argmax(diffs)) + 1

    return int(np.clip(elbow, min_k, max_k))
