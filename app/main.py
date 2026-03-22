from app.routes.enhance import router as enhance_router

from fastapi import FastAPI

app = FastAPI()


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


app.include_router(enhance_router, prefix="/api")
