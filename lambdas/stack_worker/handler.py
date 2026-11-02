import logging
import os

import cv2

from app.services.stack_pipeline import run_stack

# Lambda's root logger already has a handler; it just defaults to WARNING.
logging.getLogger().setLevel(logging.INFO)

# Match Render for the M1 parity check — threading gets re-tested in M7.
cv2.setNumThreads(1)

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/tmp")


def handler(event, context):
    """M1: stack a local video file. S3 input/output replaces this in M3.

    Event: {"video_path": "/videos/moon2.mp4", "top_percent": 0}
    """
    video_path = event["video_path"]
    top_percent = float(event.get("top_percent", 0.0))
    filename = os.path.basename(video_path)

    with open(video_path, "rb") as f:
        data = f.read()

    png, stats = run_stack(data, filename, top_percent)

    output_path = os.path.join(
        OUTPUT_DIR, f"{os.path.splitext(filename)[0]}_stacked.png"
    )
    with open(output_path, "wb") as f:
        f.write(png)

    return {"output_path": output_path, **stats}
