from __future__ import annotations

from fastapi import BackgroundTasks, FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import json
import shutil
import uuid

from pipeline import extract_audio, separate_vocals, transcribe, make_ass, render_video

app = FastAPI(title="KaraokeForge Worker", version="0.3.0")
ROOT = Path("jobs")
ROOT.mkdir(exist_ok=True)


def process_job(job_id: str) -> None:
    job = ROOT / job_id
    source = next(job.glob("source.*"))
    audio = job / "audio.wav"
    stems = job / "stems"
    stems.mkdir(exist_ok=True)
    try:
        (job / "status.json").write_text(json.dumps({"status": "extracting"}))
        extract_audio(source, audio)
        (job / "status.json").write_text(json.dumps({"status": "separating"}))
        instrumental = separate_vocals(audio, stems)
        vocal_candidates = list(stems.glob("**/vocals.wav"))
        if not vocal_candidates:
            raise FileNotFoundError("Demucs did not produce vocals.wav")
        (job / "status.json").write_text(json.dumps({"status": "transcribing"}))
        segments = transcribe(vocal_candidates[0])
        (job / "lyrics.json").write_text(json.dumps(segments, ensure_ascii=False, indent=2))
        ass = job / "lyrics.ass"
        make_ass(segments, ass)
        (job / "status.json").write_text(json.dumps({"status": "rendering"}))
        output = job / "karaokeforge.mp4"
        render_video(instrumental, source, ass, output)
        (job / "status.json").write_text(json.dumps({"status": "complete", "download": f"/jobs/{job_id}/download"}))
    except Exception as exc:
        (job / "status.json").write_text(json.dumps({"status": "failed", "error": str(exc)}))


@app.get("/health")
def health():
    return {"status": "ok", "service": "karaokeforge-worker"}


@app.post("/jobs")
async def create_job(background: BackgroundTasks, file: UploadFile = File(...)):
    job_id = uuid.uuid4().hex
    job = ROOT / job_id
    job.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "upload.bin").suffix.lower()
    source = job / f"source{suffix}"
    with source.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    (job / "status.json").write_text(json.dumps({"status": "queued"}))
    background.add_task(process_job, job_id)
    return {"jobId": job_id, "status": "queued", "filename": file.filename}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = ROOT / job_id
    status = job / "status.json"
    if not status.exists():
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return json.loads(status.read_text()) | {"jobId": job_id}


@app.get("/jobs/{job_id}/download")
def download(job_id: str):
    output = ROOT / job_id / "karaokeforge.mp4"
    if not output.exists():
        return JSONResponse({"error": "Video is not ready"}, status_code=404)
    return FileResponse(output, media_type="video/mp4", filename="karaokeforge.mp4")
