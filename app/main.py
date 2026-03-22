from fastapi import FastAPI, File, UploadFile

app = FastAPI()


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/upload-test")
async def upload_test(file: UploadFile = File(...)):
    return {
        "filename": file.filename,
        "content_type": file.content_type,
    }
