from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from pathlib import Path
import uuid
import shutil

app = FastAPI(title="KaraokeForge Worker", version="0.2.0")
ROOT = Path("jobs")
ROOT.mkdir(exist_ok=True)

@app.get("/health")
def health():
    return {"status": "ok", "service": "karaokeforge-worker"}

@app.post("/jobs")
async def create_job(file: UploadFile = File(...)):
    job_id = uuid.uuid4().hex
    job_dir = ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "upload.bin").suffix.lower()
    source = job_dir / f"source{suffix}"
    with source.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    return JSONResponse({"jobId": job_id, "status": "queued", "filename": file.filename})

@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job_dir = ROOT / job_id
    if not job_dir.exists():
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return {"jobId": job_id, "status": "queued", "files": [p.name for p in job_dir.iterdir()]}
