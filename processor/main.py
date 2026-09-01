from pathlib import Path
import subprocess
import tempfile
import uuid

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from faster_whisper import WhisperModel

app = FastAPI(title="KaraokeForge Processor")
ROOT = Path(__file__).resolve().parent
WORK = ROOT / "jobs"
WORK.mkdir(exist_ok=True)

_model = None

def whisper_model():
    global _model
    if _model is None:
        _model = WhisperModel("small", device="cuda", compute_type="float16")
    return _model

def run(cmd: list[str]):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:])

def make_ass(segments, path: Path):
    def ass_time(seconds: float) -> str:
        h = int(seconds // 3600); m = int((seconds % 3600) // 60); s = seconds % 60
        return f"{h}:{m:02d}:{s:05.2f}"
    lines = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080", "", "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding", "Style: Karaoke,Arial,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,-1,0,1,3,1,2,80,80,70,1", "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for seg in segments:
        text = seg.text.strip().replace("{", "(").replace("}", ")")
        lines.append(f"Dialogue: 0,{ass_time(seg.start)},{ass_time(seg.end)},Karaoke,,0,0,0,,{text}")
    path.write_text("\n".join(lines), encoding="utf-8")

@app.get("/health")
def health():
    return {"ok": True, "service": "karaokeforge-processor"}

@app.post("/process")
async def process(file: UploadFile = File(...)):
    suffix = Path(file.filename or "input").suffix.lower()
    if suffix not in {".mp3", ".wav", ".m4a", ".mp4", ".mov", ".webm"}:
        raise HTTPException(400, "Unsupported media format")
    job = WORK / str(uuid.uuid4())
    job.mkdir()
    source = job / f"source{suffix}"
    source.write_bytes(await file.read())
    audio = job / "audio.wav"
    instrumental = job / "instrumental.wav"
    lyrics = job / "lyrics.ass"
    output = job / "karaoke.mp4"

    # Normalize/extract audio.
    run(["ffmpeg", "-y", "-i", str(source), "-vn", "-ac", "2", "-ar", "44100", str(audio)])
    # Demucs writes separated stems into the output directory.
    sep = job / "separated"
    run(["python", "-m", "demucs", "--two-stems=vocals", "-o", str(sep), str(audio)])
    candidates = list(sep.rglob("no_vocals.wav"))
    if not candidates:
        raise RuntimeError("Demucs did not produce an instrumental stem")
    candidates[0].replace(instrumental)

    model = whisper_model()
    segments, _ = model.transcribe(str(audio), beam_size=5, word_timestamps=False)
    segments = list(segments)
    make_ass(segments, lyrics)

    # Dark cinematic karaoke canvas with synced ASS subtitles.
    run(["ffmpeg", "-y", "-i", str(instrumental), "-vf", f"ass={lyrics}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", str(output)])
    return FileResponse(output, media_type="video/mp4", filename="karaoke.mp4")
