from __future__ import annotations

from fastapi import BackgroundTasks, FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import json
import shutil
import time
import uuid

from pipeline import extract_audio, separate_vocals, transcribe, make_ass, render_video

app = FastAPI(title="KaraokeForge Worker", version="0.4.0")
ROOT = Path("jobs")
ROOT.mkdir(exist_ok=True)

STAGES = {
    "queued": (0, "Waiting to start"),
    "extracting": (15, "Preparing audio"),
    "separating": (40, "Removing vocals"),
    "transcribing": (65, "Transcribing lyrics"),
    "rendering": (88, "Rendering karaoke video"),
    "complete": (100, "Karaoke ready"),
}


def write_status(job: Path, status: str, **extra) -> None:
    payload = {"status": status, "progress": STAGES.get(status, (0, status))[0], "message": STAGES.get(status, (0, status))[1], "updatedAt": time.time(), **extra}
    (job / "status.json").write_text(json.dumps(payload), encoding="utf-8")


def process_job(job_id: str) -> None:
    job = ROOT / job_id
    source_files = list(job.glob("source.*"))
    if not source_files:
        write_status(job, "failed", error="Source file is missing.")
        return
    source = source_files[0]
    audio = job / "audio.wav"
    stems = job / "stems"
    stems.mkdir(exist_ok=True)
    try:
        write_status(job, "extracting")
        extract_audio(source, audio)

        write_status(job, "separating")
        instrumental = separate_vocals(audio, stems)
        vocal_candidates = list(stems.glob("**/vocals.wav"))
        if not vocal_candidates:
            raise FileNotFoundError("Demucs did not produce vocals.wav")

        write_status(job, "transcribing")
        segments = transcribe(vocal_candidates[0])
        (job / "lyrics.json").write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
        ass = job / "lyrics.ass"
        make_ass(segments, ass)

        write_status(job, "rendering")
        output = job / "karaokeforge.mp4"
        render_video(instrumental, source, ass, output)
        write_status(job, "complete", download=f"/jobs/{job_id}/download", lyrics=f"/jobs/{job_id}/lyrics")
    except Exception as exc:
        write_status(job, "failed", error=f"{type(exc).__name__}: {exc}")


@app.get("/health")
def health():
    return {"status": "ok", "service": "karaokeforge-worker", "jobs": len(list(ROOT.iterdir()))}


@app.post("/jobs")
async def create_job(background: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename:
        return JSONResponse({"error": "A filename is required."}, status_code=400)
    job_id = uuid.uuid4().hex
    job = ROOT / job_id
    job.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename).suffix.lower() or ".bin"
    source = job / f"source{suffix}"
    with source.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    write_status(job, "queued", filename=file.filename)
    background.add_task(process_job, job_id)
    return {"jobId": job_id, "status": "queued", "filename": file.filename}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = ROOT / job_id
    status = job / "status.json"
    if not status.exists():
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return json.loads(status.read_text(encoding="utf-8")) | {"jobId": job_id}


@app.get("/jobs/{job_id}/lyrics")
def lyrics(job_id: str):
    target = ROOT / job_id / "lyrics.json"
    if not target.exists():
        return JSONResponse({"error": "Lyrics are not ready"}, status_code=404)
    return json.loads(target.read_text(encoding="utf-8"))


@app.get("/jobs/{job_id}/download")
def download(job_id: str):
    output = ROOT / job_id / "karaokeforge.mp4"
    if not output.exists():
        return JSONResponse({"error": "Video is not ready"}, status_code=404)
    return FileResponse(output, media_type="video/mp4", filename="karaokeforge.mp4")
