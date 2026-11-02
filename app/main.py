from app.routes.enhance import router as enhance_router
from app.routes.stack import router as stack_router
from app.routes.background import router as background_router

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import logging
import os
import cv2
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

# Route handlers that do heavy CV2 work run in a worker thread (see stack.py),
# so OpenCV's own internal thread pool can now be entered from a non-main
# thread for the first time. Mixing OpenCV's internal threading with the
# application's own threading is a known source of native-level crashes
# (segfaults) rather than catchable Python exceptions — disable it since
# nothing here benefits from OpenCV parallelizing within a single call.
cv2.setNumThreads(1)


app = FastAPI()

origins = os.getenv("ALLOWED_ORIGINS").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


app.include_router(enhance_router, prefix="/api")
app.include_router(stack_router, prefix="/api")
app.include_router(background_router, prefix="/api")
