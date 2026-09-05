import os
import struct
import tempfile
from collections.abc import Callable, Iterator

import cv2
import numpy as np

_SER_COLOR_MONO = 0
_SER_COLOR_BAYER_RGGB = 8
_SER_COLOR_BAYER_GRBG = 9
_SER_COLOR_BAYER_GBRG = 10
_SER_COLOR_BAYER_BGGR = 11
_SER_COLOR_BGR = 16
_SER_COLOR_RGB = 18

_BAYER_CODES = {
    _SER_COLOR_BAYER_RGGB: cv2.COLOR_BAYER_RG2RGB,
    _SER_COLOR_BAYER_GRBG: cv2.COLOR_BAYER_GR2RGB,
    _SER_COLOR_BAYER_GBRG: cv2.COLOR_BAYER_GB2RGB,
    _SER_COLOR_BAYER_BGGR: cv2.COLOR_BAYER_BG2RGB,
}

ScoreFn = Callable[[np.ndarray], float]


def score_frames_streaming(data: bytes, filename: str, score_fn: ScoreFn) -> list[float]:
    """Scores every frame one at a time, discarding each after scoring.

    Peak memory stays O(1 frame) regardless of video length, unlike decoding
    the whole video into a list up front.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".ser":
        return _score_ser(data, score_fn)
    return _score_video(data, score_fn, ext)


def extract_frames_by_index_streaming(
    data: bytes, filename: str, indices: list[int]
) -> Iterator[tuple[int, np.ndarray]]:
    """Yields (index, frame) pairs for `indices`, decoding one at a time.

    Never buffers more than the current frame, regardless of how many
    indices are requested — unlike `extract_frames_by_index`, which needs to
    hold every requested frame in memory to hand back a list.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".ser":
        yield from _extract_ser_by_index_streaming(data, indices)
    else:
        yield from _extract_video_by_index_streaming(data, indices, ext)


def extract_frames_by_index(
    data: bytes, filename: str, indices: list[int]
) -> list[np.ndarray]:
    """Decodes and returns only the frames at `indices`, in that same order.

    Only use this for a small number of indices (e.g. a single reference
    frame) — for the full selected set, consume
    `extract_frames_by_index_streaming` instead so frames aren't all held
    in memory at once.
    """
    frames_by_index = dict(extract_frames_by_index_streaming(data, filename, indices))
    return [frames_by_index[i] for i in indices if i in frames_by_index]


def _score_video(data: bytes, score_fn: ScoreFn, ext: str) -> list[float]:
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(data)
        tmp_path = f.name
    try:
        cap = cv2.VideoCapture(tmp_path)
        scores = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            scores.append(score_fn(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        cap.release()
    finally:
        os.unlink(tmp_path)
    if not scores:
        raise ValueError("No frames could be read from video file")
    return scores


def _extract_video_by_index_streaming(
    data: bytes, indices: list[int], ext: str
) -> Iterator[tuple[int, np.ndarray]]:
    wanted = set(indices)
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(data)
        tmp_path = f.name
    try:
        cap = cv2.VideoCapture(tmp_path)
        idx = 0
        while wanted:
            if idx in wanted:
                ret, frame = cap.read()
                if not ret:
                    break
                yield idx, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                wanted.discard(idx)
            else:
                ret = cap.grab()
                if not ret:
                    break
            idx += 1
        cap.release()
    finally:
        os.unlink(tmp_path)


def _parse_ser_header(data: bytes) -> dict:
    if len(data) < 178:
        raise ValueError("File too small to be a valid SER file")

    header = data[:178]
    color_id = struct.unpack_from("<i", header, 14)[0]
    width = struct.unpack_from("<i", header, 26)[0]
    height = struct.unpack_from("<i", header, 30)[0]
    bit_depth = struct.unpack_from("<i", header, 34)[0]
    frame_count = struct.unpack_from("<i", header, 38)[0]

    bytes_per_sample = 2 if bit_depth > 8 else 1
    channels = 3 if color_id in (_SER_COLOR_BGR, _SER_COLOR_RGB) else 1
    frame_bytes = width * height * channels * bytes_per_sample

    return {
        "color_id": color_id,
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "frame_count": frame_count,
        "bytes_per_sample": bytes_per_sample,
        "channels": channels,
        "frame_bytes": frame_bytes,
    }


def _decode_ser_frame(data: bytes, meta: dict, index: int) -> np.ndarray | None:
    offset = 178 + index * meta["frame_bytes"]
    raw = data[offset : offset + meta["frame_bytes"]]
    if len(raw) < meta["frame_bytes"]:
        return None

    dtype = np.uint16 if meta["bytes_per_sample"] == 2 else np.uint8
    channels = meta["channels"]
    height, width = meta["height"], meta["width"]
    arr = (
        np.frombuffer(raw, dtype=dtype).reshape(height, width, channels)
        if channels > 1
        else np.frombuffer(raw, dtype=dtype).reshape(height, width)
    )

    if meta["bytes_per_sample"] == 2:
        arr = (arr >> (meta["bit_depth"] - 8)).astype(np.uint8)

    color_id = meta["color_id"]
    if color_id in _BAYER_CODES:
        arr = cv2.cvtColor(arr, _BAYER_CODES[color_id])
    elif color_id == _SER_COLOR_BGR:
        arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
    elif color_id == _SER_COLOR_MONO:
        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)

    return arr


def _score_ser(data: bytes, score_fn: ScoreFn) -> list[float]:
    meta = _parse_ser_header(data)
    scores = []
    for i in range(meta["frame_count"]):
        frame = _decode_ser_frame(data, meta, i)
        if frame is None:
            break
        scores.append(score_fn(frame))
    if not scores:
        raise ValueError("No frames could be read from SER file")
    return scores


def _extract_ser_by_index_streaming(
    data: bytes, indices: list[int]
) -> Iterator[tuple[int, np.ndarray]]:
    meta = _parse_ser_header(data)
    for i in sorted(indices):
        frame = _decode_ser_frame(data, meta, i)
        if frame is not None:
            yield i, frame
