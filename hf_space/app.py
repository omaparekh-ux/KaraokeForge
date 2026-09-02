from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import spaces
import gradio as gr

BASE = Path(os.getenv("KARAOKEFORGE_WORK_DIR", "/tmp/karaokeforge"))
BASE.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "250"))
DEMUCS_MODEL = os.getenv("DEMUCS_MODEL", "htdemucs")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
VIDEO_PRESET = os.getenv("VIDEO_PRESET", "medium")


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown processing error").strip()
        raise RuntimeError(f"Command failed ({result.returncode}): {detail[-2000:]}")


def safe_stem(filename: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).stem).strip("._")
    return stem[:80] or "karaoke"


def ass_time(seconds: float) -> str:
    total = max(0, int(round(seconds * 100)))
    hours, rest = divmod(total, 360000)
    minutes, rest = divmod(rest, 6000)
    secs, centis = divmod(rest, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def escape_ass(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", " ").strip()


def wrap_words(words: list[dict[str, Any]], max_chars: int = 42) -> list[list[dict[str, Any]]]:
    lines: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    size = 0
    for word in words:
        extra = len(word["text"]) + (1 if current else 0)
        if current and size + extra > max_chars:
            lines.append(current)
            current = []
            size = 0
        current.append(word)
        size += extra
    if current:
        lines.append(current)
    return lines


def make_ass(segments: list[dict[str, Any]], target: Path) -> None:
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1920",
        "PlayResY: 1080",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Karaoke,DejaVu Sans,64,&H0000D7FF,&H00FFFFFF,&H00101010,&H99000000,-1,0,0,0,100,100,0,0,1,4,2,2,120,120,100,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for segment in segments:
        words = segment.get("words") or []
        if not words:
            lines.append(
                f"Dialogue: 0,{ass_time(segment['start'])},{ass_time(segment['end'])},Karaoke,,0,0,0,,{escape_ass(segment.get('text', ''))}"
            )
            continue
        for line_words in wrap_words(words):
            chunks = [
                f"{{\\k{max(1, int(round((word['end'] - word['start']) * 100)))}}}{escape_ass(word['text'])}"
                for word in line_words
            ]
            payload = " ".join(chunks)
            lines.append(
                f"Dialogue: 0,{ass_time(line_words[0]['start'])},{ass_time(line_words[-1]['end'])},Karaoke,,0,0,0,,{payload}"
            )
    target.write_text("\n".join(lines), encoding="utf-8")


def has_video(source: Path) -> bool:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_type", "-of", "json", str(source)],
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        return bool(json.loads(result.stdout or "{}").get("streams"))
    except json.JSONDecodeError:
        return False


def media_duration(source: Path) -> str:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(source)],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip()


def clean_old_outputs(max_age_hours: int = 12) -> None:
    cutoff = time.time() - max_age_hours * 3600
    for item in BASE.iterdir():
        try:
            if item.stat().st_mtime < cutoff:
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
        except OSError:
            continue


@spaces.GPU(duration=300)
def forge(media: str, progress: gr.Progress = gr.Progress(track_tqdm=True)):
    """Turn one uploaded song into a karaoke MP4, instrumental WAV, lyrics JSON and ASS subtitles."""
    if not media:
        raise gr.Error("Upload an audio or video file first.")

    source_path = Path(media)
    if not source_path.exists():
        raise gr.Error("The uploaded file is no longer available. Please upload it again.")
    if source_path.stat().st_size > MAX_UPLOAD_MB * 1024 * 1024:
        raise gr.Error(f"Files are limited to {MAX_UPLOAD_MB} MB.")
    if source_path.suffix.lower() not in {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".mp4", ".mov", ".mkv", ".webm"}:
        raise gr.Error("Unsupported media format.")

    clean_old_outputs()
    job_dir = BASE / uuid.uuid4().hex
    job_dir.mkdir(parents=True, exist_ok=True)
    source = job_dir / f"source{source_path.suffix.lower()}"
    shutil.copy2(source_path, source)

    try:
        progress(0.05, desc="Preparing audio")
        audio = job_dir / "audio.wav"
        run(["ffmpeg", "-y", "-i", str(source), "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(audio)])

        progress(0.20, desc="Removing vocals")
        separated = job_dir / "separated"
        run(["python", "-m", "demucs", "--two-stems=vocals", "-n", DEMUCS_MODEL, "-d", "cuda", "-o", str(separated), str(audio)])
        instrumental_candidates = list(separated.glob("**/no_vocals.wav"))
        vocal_candidates = list(separated.glob("**/vocals.wav"))
        if not instrumental_candidates or not vocal_candidates:
            raise RuntimeError("Demucs did not produce both vocal and instrumental stems.")
        instrumental = job_dir / "instrumental.wav"
        shutil.copy2(instrumental_candidates[0], instrumental)

        progress(0.50, desc="Transcribing lyrics")
        from faster_whisper import WhisperModel
        model = WhisperModel(WHISPER_MODEL, device="cuda", compute_type="float16")
        segments_iter, _ = model.transcribe(
            str(vocal_candidates[0]),
            word_timestamps=True,
            vad_filter=True,
            beam_size=5,
            condition_on_previous_text=True,
        )
        segments: list[dict[str, Any]] = []
        for segment in segments_iter:
            words: list[dict[str, Any]] = []
            for word in segment.words or []:
                if word.start is None or word.end is None:
                    continue
                text = word.word.strip()
                if text:
                    words.append({"text": text, "start": float(word.start), "end": float(word.end)})
            text = " ".join(word["text"] for word in words).strip() or segment.text.strip()
            if text:
                segments.append({"text": text, "start": float(segment.start), "end": float(segment.end), "words": words})

        lyrics_json = job_dir / "lyrics.json"
        lyrics_json.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
        ass = job_dir / "lyrics.ass"
        make_ass(segments, ass)

        progress(0.75, desc="Rendering karaoke video")
        output = job_dir / f"{safe_stem(source.name)}_karaoke.mp4"
        if has_video(source):
            cmd = [
                "ffmpeg", "-y", "-i", str(source), "-i", str(instrumental),
                "-map", "0:v:0", "-map", "1:a:0", "-vf", f"ass={ass}",
                "-c:v", "libx264", "-preset", VIDEO_PRESET, "-crf", "19",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest",
                "-movflags", "+faststart", str(output),
            ]
        else:
            duration = media_duration(instrumental)
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x09090b:s=1920x1080:r=30",
                "-i", str(instrumental), "-t", duration or "0", "-vf", f"ass={ass}",
                "-c:v", "libx264", "-preset", VIDEO_PRESET, "-crf", "20",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest",
                "-movflags", "+faststart", str(output),
            ]
        run(cmd)
        progress(1.0, desc="Karaoke ready")
        return str(output), str(instrumental), str(lyrics_json), str(ass)
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise


demo = gr.Interface(
    fn=forge,
    inputs=gr.File(
        label="Song audio or video",
        file_count="single",
        type="filepath",
        file_types=[".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".mp4", ".mov", ".mkv", ".webm"],
    ),
    outputs=[
        gr.Video(label="Karaoke MP4"),
        gr.Audio(label="Instrumental WAV", type="filepath"),
        gr.File(label="Lyrics JSON"),
        gr.File(label="ASS subtitles"),
    ],
    title="KaraokeForge",
    description="Upload a song. KaraokeForge separates the lead vocal, creates word-timed lyrics, and renders a 1080p karaoke video. Processing uses open-source Demucs, faster-whisper and FFmpeg.",
    api_name="forge",
)

demo.queue(max_size=3, default_concurrency_limit=1).launch()
