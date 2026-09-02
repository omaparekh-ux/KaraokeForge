from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from job_store import count_jobs, create_job, get_job as get_stored_job, queued_jobs, reset_running_jobs, update_job
from pipeline import extract_audio, make_ass, render_video, separate_vocals, transcribe

ROOT = Path(os.getenv("JOBS_DIR", "jobs"))
ROOT.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "250"))
MAX_CONCURRENT_JOBS = max(1, int(os.getenv("MAX_CONCURRENT_JOBS", "1")))
JOB_TTL_HOURS = max(1, int(os.getenv("JOB_TTL_HOURS", "24")))
# The worker is normally exposed through a temporary public tunnel. Wildcard CORS is safe here because
# the API does not use browser cookies or credentials. Operators can still lock it down with an explicit list.
FRONTEND_ORIGINS = [origin.strip() for origin in os.getenv("FRONTEND_ORIGINS", "*").split(",") if origin.strip()]

STAGES = {
    "queued": (0, "Waiting to start"),
    "running": (5, "Starting karaoke pipeline"),
    "extracting": (15, "Preparing audio"),
    "separating": (40, "Removing vocals"),
    "transcribing": (65, "Transcribing lyrics"),
    "rendering": (88, "Rendering karaoke video"),
    "complete": (100, "Karaoke ready"),
}
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".mp4", ".mov", ".mkv", ".webm"}
JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")
EXECUTOR = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS)


def _job_path(job_id: str) -> Path:
    if not JOB_ID_RE.fullmatch(job_id):
        raise ValueError("Invalid job id")
    return ROOT / job_id


def _safe_stem(filename: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).stem).strip("._")
    return stem[:80] or "karaoke"


def _write_status(job: Path, status: str, **extra: object) -> None:
    progress, message = STAGES.get(status, (0, status))
    payload = {"status": status, "progress": progress, "message": message, "updatedAt": time.time(), **extra}
    (job / "status.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _set_status(job_id: str, status: str, **extra: object) -> None:
    job = _job_path(job_id)
    progress, message = STAGES.get(status, (0, status))
    update_job(job_id, status=status, progress=progress, message=message, error=str(extra["error"]) if "error" in extra else None)
    _write_status(job, status, **extra)


def _cleanup_stale_jobs() -> int:
    cutoff = time.time() - JOB_TTL_HOURS * 3600
    removed = 0
    for job in ROOT.iterdir():
        if not job.is_dir() or not JOB_ID_RE.fullmatch(job.name):
            continue
        status_file = job / "status.json"
        try:
            updated = status_file.stat().st_mtime if status_file.exists() else job.stat().st_mtime
            status = json.loads(status_file.read_text(encoding="utf-8")).get("status") if status_file.exists() else None
        except (OSError, json.JSONDecodeError):
            continue
        if updated < cutoff and status in {"complete", "failed"}:
            shutil.rmtree(job, ignore_errors=True)
            removed += 1
    return removed


def process_job(job_id: str) -> None:
    job = _job_path(job_id)
    sources = list(job.glob("source.*"))
    if not sources:
        _set_status(job_id, "failed", error="Source media is missing.")
        return
    source = sources[0]
    audio = job / "audio.wav"
    stems = job / "stems"
    stems.mkdir(exist_ok=True)
    try:
        _set_status(job_id, "running")
        _set_status(job_id, "extracting")
        extract_audio(source, audio)

        _set_status(job_id, "separating")
        instrumental = separate_vocals(audio, stems)
        vocal_candidates = list(stems.glob("**/vocals.wav"))
        if not vocal_candidates:
            raise FileNotFoundError("Demucs did not produce vocals.wav")

        _set_status(job_id, "transcribing")
        segments = transcribe(vocal_candidates[0])
        (job / "lyrics.json").write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
        ass = job / "lyrics.ass"
        make_ass(segments, ass)

        _set_status(job_id, "rendering")
        output = job / "karaokeforge.mp4"
        render_video(instrumental, source, ass, output)
        _set_status(job_id, "complete", filename=source.name, title=source.stem, lyrics=f"/jobs/{job_id}/lyrics", download=f"/jobs/{job_id}/download", preview=f"/jobs/{job_id}/preview", instrumental=f"/jobs/{job_id}/instrumental", subtitles=f"/jobs/{job_id}/subtitles", wordCount=sum(len(segment.get("words", [])) for segment in segments), segmentCount=len(segments))
    except Exception as exc:
        _set_status(job_id, "failed", error=f"{type(exc).__name__}: {exc}")


def _submit(job_id: str) -> None:
    EXECUTOR.submit(process_job, job_id)


@asynccontextmanager
async def lifespan(_: FastAPI):
    reset_running_jobs()
    _cleanup_stale_jobs()
    for job_id in queued_jobs():
        _submit(job_id)
    yield
    EXECUTOR.shutdown(wait=False, cancel_futures=False)


app = FastAPI(title="KaraokeForge Worker", version="0.9.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"]
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "karaokeforge-worker",
        "jobs": count_jobs(),
        "maxConcurrentJobs": MAX_CONCURRENT_JOBS,
        "maxUploadMB": MAX_UPLOAD_MB,
        "jobTtlHours": JOB_TTL_HOURS,
    }


@app.post("/jobs")
async def create_new_job(file: UploadFile = File(...)):
    if not file.filename:
        return JSONResponse({"error": "A filename is required."}, status_code=400)
    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        return JSONResponse({"error": f"Unsupported file type: {extension or 'unknown'}"}, status_code=415)
    job_id = uuid.uuid4().hex
    job = ROOT / job_id
    job.mkdir(parents=True, exist_ok=True)
    safe_name = f"{_safe_stem(file.filename)}{extension}"
    source = job / f"source{extension}"
    total = 0
    limit = MAX_UPLOAD_MB * 1024 * 1024
    try:
        with source.open("wb") as out:
            while True:
                chunk = await file.read(8 * 1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise ValueError(f"File is larger than the {MAX_UPLOAD_MB} MB limit.")
                out.write(chunk)
    except ValueError as exc:
        shutil.rmtree(job, ignore_errors=True)
        return JSONResponse({"error": str(exc)}, status_code=413)
    create_job(job_id, safe_name)
    _write_status(job, "queued", filename=safe_name, sizeBytes=total)
    _submit(job_id)
    return {"jobId": job_id, "status": "queued", "filename": safe_name}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    try:
        stored = get_stored_job(job_id)
        job = _job_path(job_id)
    except ValueError:
        return JSONResponse({"error": "Invalid job id"}, status_code=400)
    if not stored or not job.exists():
        return JSONResponse({"error": "Job not found"}, status_code=404)
    status_file = job / "status.json"
    status = json.loads(status_file.read_text(encoding="utf-8")) if status_file.exists() else {}
    return {**stored, **status, "jobId": job_id}


@app.get("/jobs/{job_id}/lyrics")
def lyrics(job_id: str):
    try:
        target = _job_path(job_id) / "lyrics.json"
    except ValueError:
        return JSONResponse({"error": "Invalid job id"}, status_code=400)
    if not target.exists():
        return JSONResponse({"error": "Lyrics are not ready"}, status_code=404)
    return json.loads(target.read_text(encoding="utf-8"))


@app.get("/jobs/{job_id}/subtitles")
def subtitles(job_id: str):
    try:
        target = _job_path(job_id) / "lyrics.ass"
    except ValueError:
        return JSONResponse({"error": "Invalid job id"}, status_code=400)
    if not target.exists():
        return JSONResponse({"error": "Subtitles are not ready"}, status_code=404)
    return FileResponse(target, media_type="text/plain", filename="lyrics.ass", headers={"Cache-Control": "private, no-store"})


@app.get("/jobs/{job_id}/preview")
def preview(job_id: str):
    try:
        output = _job_path(job_id) / "karaokeforge.mp4"
    except ValueError:
        return JSONResponse({"error": "Invalid job id"}, status_code=400)
    if not output.exists():
        return JSONResponse({"error": "Video is not ready"}, status_code=404)
    return FileResponse(output, media_type="video/mp4", filename="karaokeforge.mp4", headers={"Content-Disposition": "inline", "Cache-Control": "private, no-store"})


@app.get("/jobs/{job_id}/download")
def download(job_id: str):
    try:
        output = _job_path(job_id) / "karaokeforge.mp4"
    except ValueError:
        return JSONResponse({"error": "Invalid job id"}, status_code=400)
    if not output.exists():
        return JSONResponse({"error": "Video is not ready"}, status_code=404)
    job = get_stored_job(job_id) or {}
    filename = f"{_safe_stem(str(job.get('filename', 'karaokeforge')))}_karaoke.mp4"
    return FileResponse(output, media_type="video/mp4", filename=filename, headers={"Cache-Control": "private, no-store"})


@app.get("/jobs/{job_id}/instrumental")
def instrumental_download(job_id: str):
    try:
        candidates = list((_job_path(job_id) / "stems").glob("**/no_vocals.wav"))
    except ValueError:
        return JSONResponse({"error": "Invalid job id"}, status_code=400)
    if not candidates:
        return JSONResponse({"error": "Instrumental track is not ready"}, status_code=404)
    job = get_stored_job(job_id) or {}
    filename = f"{_safe_stem(str(job.get('filename', 'karaokeforge')))}_instrumental.wav"
    return FileResponse(candidates[0], media_type="audio/wav", filename=filename, headers={"Cache-Control": "private, no-store"})
