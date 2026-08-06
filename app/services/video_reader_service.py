import os
import struct
import tempfile

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


def extract_frames(data: bytes, filename: str) -> list[np.ndarray]:
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".ser":
        return _read_ser(data)
    return _read_video(data, ext)


def _read_video(data: bytes, ext: str) -> list[np.ndarray]:
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(data)
        tmp_path = f.name
    try:
        cap = cv2.VideoCapture(tmp_path)
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        cap.release()
    finally:
        os.unlink(tmp_path)
    if not frames:
        raise ValueError("No frames could be read from AVI file")
    return frames


def _read_ser(data: bytes) -> list[np.ndarray]:
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

    frames = []
    offset = 178
    for _ in range(frame_count):
        raw = data[offset : offset + frame_bytes]
        offset += frame_bytes
        if len(raw) < frame_bytes:
            break

        dtype = np.uint16 if bytes_per_sample == 2 else np.uint8
        arr = (
            np.frombuffer(raw, dtype=dtype).reshape(height, width, channels)
            if channels > 1
            else np.frombuffer(raw, dtype=dtype).reshape(height, width)
        )

        if bytes_per_sample == 2:
            arr = (arr >> (bit_depth - 8)).astype(np.uint8)

        if color_id in _BAYER_CODES:
            arr = cv2.cvtColor(arr, _BAYER_CODES[color_id])
        elif color_id == _SER_COLOR_BGR:
            arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        elif color_id == _SER_COLOR_MONO:
            arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)

        frames.append(arr)

    if not frames:
        raise ValueError("No frames could be read from SER file")
    return frames
