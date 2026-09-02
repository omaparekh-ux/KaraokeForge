from __future__ import annotations
import json, os, re, shutil, time, uuid
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from job_store import count_jobs, create_job, get_job as get_stored_job, queued_jobs, reset_running_jobs, update_job
from pipeline import extract_audio, separate_vocals, transcribe, make_ass, render_video
ROOT=Path(os.getenv("JOBS_DIR","jobs")); ROOT.mkdir(parents=True,exist_ok=True)
MAX_UPLOAD_MB=int(os.getenv("MAX_UPLOAD_MB","250")); MAX_CONCURRENT_JOBS=max(1,int(os.getenv("MAX_CONCURRENT_JOBS","1")))
STAGES={"queued":(0,"Waiting to start"),"running":(5,"Starting karaoke pipeline"),"extracting":(15,"Preparing audio"),"separating":(40,"Removing vocals"),"transcribing":(65,"Transcribing lyrics"),"rendering":(88,"Rendering karaoke video"),"complete":(100,"Karaoke ready")}
ALLOWED_EXTENSIONS={".mp3",".wav",".m4a",".aac",".flac",".ogg",".mp4",".mov",".mkv",".webm"}; EXECUTOR=ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS)
def _job_path(job_id:str)->Path:return ROOT/job_id
def _safe_stem(filename:str)->str:return (re.sub(r"[^A-Za-z0-9._-]+","_",Path(filename).stem).strip("._")[:80] or "karaoke")
def _write_status(job:Path,status:str,**extra:object)->None:
    progress,message=STAGES.get(status,(0,status)); payload={"status":status,"progress":progress,"message":message,"updatedAt":time.time(),**extra}; (job/"status.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
def _set_status(job_id:str,status:str,**extra:object)->None:
    job=_job_path(job_id); progress,message=STAGES.get(status,(0,status)); update_job(job_id,status=status,progress=progress,message=message,error=str(extra["error"]) if "error" in extra else None); _write_status(job,status,**extra)
def process_job(job_id:str)->None:
    job=_job_path(job_id); sources=list(job.glob("source.*"))
    if not sources:_set_status(job_id,"failed",error="Source media is missing."); return
    source=sources[0]; audio=job/"audio.wav"; stems=job/"stems"; stems.mkdir(exist_ok=True)
    try:
        _set_status(job_id,"running"); _set_status(job_id,"extracting"); extract_audio(source,audio)
        _set_status(job_id,"separating"); instrumental=separate_vocals(audio,stems); vocal=list(stems.glob("**/vocals.wav"))
        if not vocal: raise FileNotFoundError("Demucs did not produce vocals.wav")
        _set_status(job_id,"transcribing"); segments=transcribe(vocal[0]); (job/"lyrics.json").write_text(json.dumps(segments,ensure_ascii=False,indent=2),encoding="utf-8"); ass=job/"lyrics.ass"; make_ass(segments,ass)
        _set_status(job_id,"rendering"); output=job/"karaokeforge.mp4"; render_video(instrumental,source,ass,output)
        _set_status(job_id,"complete",filename=source.name,title=source.stem,lyrics=f"/jobs/{job_id}/lyrics",download=f"/jobs/{job_id}/download",preview=f"/jobs/{job_id}/preview",wordCount=sum(len(s.get("words",[])) for s in segments),segmentCount=len(segments))
    except Exception as exc:_set_status(job_id,"failed",error=f"{type(exc).__name__}: {exc}")
def _submit(job_id:str)->None: EXECUTOR.submit(process_job,job_id)
@asynccontextmanager
async def lifespan(_:FastAPI):
    reset_running_jobs()
    for job_id in queued_jobs(): _submit(job_id)
    yield
    EXECUTOR.shutdown(wait=False,cancel_futures=False)
app=FastAPI(title="KaraokeForge Worker",version="0.6.0",lifespan=lifespan)
@app.get("/health")
def health():return {"status":"ok","service":"karaokeforge-worker","jobs":count_jobs(),"maxConcurrentJobs":MAX_CONCURRENT_JOBS,"maxUploadMB":MAX_UPLOAD_MB}
@app.post("/jobs")
async def create_new_job(file:UploadFile=File(...)):
    if not file.filename:return JSONResponse({"error":"A filename is required."},status_code=400)
    ext=Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:return JSONResponse({"error":f"Unsupported file type: {ext or 'unknown'}"},status_code=415)
    job_id=uuid.uuid4().hex; job=_job_path(job_id); job.mkdir(parents=True,exist_ok=True); safe_name=f"{_safe_stem(file.filename)}{ext}"; source=job/f"source{ext}"
    total=0; limit=MAX_UPLOAD_MB*1024*1024
    with source.open("wb") as out:
        while True:
            chunk=await file.read(8*1024*1024)
            if not chunk:break
            total+=len(chunk)
            if total>limit:shutil.rmtree(job,ignore_errors=True);return JSONResponse({"error":f"File is larger than the {MAX_UPLOAD_MB} MB limit."},status_code=413)
            out.write(chunk)
    create_job(job_id,safe_name); _write_status(job,"queued",filename=safe_name,sizeBytes=total); _submit(job_id); return {"jobId":job_id,"status":"queued","filename":safe_name}
@app.get("/jobs/{job_id}")
def get_job(job_id:str):
    stored=get_stored_job(job_id)
    if not stored:return JSONResponse({"error":"Job not found"},status_code=404)
    status_file=_job_path(job_id)/"status.json"; status=json.loads(status_file.read_text(encoding="utf-8")) if status_file.exists() else {}; return {**stored,**status,"jobId":job_id}
@app.get("/jobs/{job_id}/lyrics")
def lyrics(job_id:str):
    target=_job_path(job_id)/"lyrics.json"
    if not target.exists():return JSONResponse({"error":"Lyrics are not ready"},status_code=404)
    return json.loads(target.read_text(encoding="utf-8"))
@app.get("/jobs/{job_id}/preview")
def preview(job_id:str):
    output=_job_path(job_id)/"karaokeforge.mp4"
    if not output.exists():return JSONResponse({"error":"Video is not ready"},status_code=404)
    return FileResponse(output,media_type="video/mp4",filename="karaokeforge.mp4",headers={"Content-Disposition":"inline","Cache-Control":"private, no-store"})
@app.get("/jobs/{job_id}/download")
def download(job_id:str):
    output=_job_path(job_id)/"karaokeforge.mp4"
    if not output.exists():return JSONResponse({"error":"Video is not ready"},status_code=404)
    job=get_stored_job(job_id) or {}; filename=f"{_safe_stem(str(job.get('filename','karaokeforge')))}_karaoke.mp4"; return FileResponse(output,media_type="video/mp4",filename=filename,headers={"Cache-Control":"private, no-store"})
