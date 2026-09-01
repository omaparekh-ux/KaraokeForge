from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def extract_audio(source: Path, wav: Path) -> None:
    run(["ffmpeg", "-y", "-i", str(source), "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(wav)])


def separate_vocals(audio: Path, out_dir: Path) -> Path:
    model = os.getenv("DEMUCS_MODEL", "htdemucs")
    run(["python", "-m", "demucs", "--two-stems=vocals", "-n", model, "-o", str(out_dir), str(audio)])
    candidates = list(out_dir.glob("**/no_vocals.wav"))
    if not candidates:
        raise FileNotFoundError("Demucs did not produce no_vocals.wav")
    return candidates[0]


def _whisper_model():
    from faster_whisper import WhisperModel
    device = os.getenv("WHISPER_DEVICE", "auto")
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
    compute = os.getenv("WHISPER_COMPUTE", "float16" if device == "cuda" else "int8")
    return WhisperModel(os.getenv("WHISPER_MODEL", "small"), device=device, compute_type=compute)


_MODEL = None


def transcribe(vocal_audio: Path) -> list[dict[str, Any]]:
    global _MODEL
    if _MODEL is None:
        _MODEL = _whisper_model()
    segments, _ = _MODEL.transcribe(str(vocal_audio), word_timestamps=True, vad_filter=True, beam_size=5)
    result: list[dict[str, Any]] = []
    for segment in segments:
        words = []
        for word in segment.words or []:
            if word.start is None or word.end is None:
                continue
            words.append({"text": word.word.strip(), "start": float(word.start), "end": float(word.end)})
        text = " ".join(w["text"] for w in words).strip() or segment.text.strip()
        if text:
            result.append({"text": text, "start": float(segment.start), "end": float(segment.end), "words": words})
    return result


def ass_time(seconds: float) -> str:
    total = max(0, int(round(seconds * 100)))
    h, rest = divmod(total, 360000)
    m, rest = divmod(rest, 6000)
    s, cs = divmod(rest, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def escape_ass(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", " ")


def make_ass(segments: list[dict[str, Any]], target: Path) -> None:
    # Primary colour is the active/highlighted colour; secondary is the upcoming lyric colour.
    lines = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080", "WrapStyle: 2", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Karaoke,Arial,62,&H0000D7FF,&H00FFFFFF,&H00101010,&H88000000,-1,0,0,0,100,100,0,0,1,3,2,2,120,120,105,1", "",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for seg in segments:
        words = seg.get("words") or []
        if words:
            chunks = []
            for word in words:
                duration_cs = max(1, int(round((word["end"] - word["start"]) * 100)))
                chunks.append(f"{{\\k{duration_cs}}}{escape_ass(word['text'])}")
            text = " ".join(chunks)
        else:
            text = escape_ass(seg.get("text", ""))
        lines.append(f"Dialogue: 0,{ass_time(seg['start'])},{ass_time(seg['end'])},Karaoke,,0,0,0,,{text}")
    target.write_text("\n".join(lines), encoding="utf-8")


def _has_video(source: Path) -> bool:
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_type", "-of", "json", str(source)], capture_output=True, text=True, check=False)
    try:
        return bool(json.loads(probe.stdout or "{}").get("streams"))
    except json.JSONDecodeError:
        return False


def render_video(instrumental: Path, source: Path, ass: Path, output: Path) -> None:
    # For video uploads, preserve the original visuals but replace its audio with the instrumental.
    # For audio-only uploads, create a clean 1080p dark canvas.
    if _has_video(source):
        cmd = ["ffmpeg", "-y", "-i", str(source), "-i", str(instrumental), "-map", "0:v:0", "-map", "1:a:0", "-vf", f"ass={ass}", "-c:v", "libx264", "-preset", os.getenv("VIDEO_PRESET", "medium"), "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", str(output)]
    else:
        duration = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(instrumental)], capture_output=True, text=True, check=False).stdout.strip()
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x09090b:s=1920x1080:r=30", "-i", str(instrumental), "-t", duration or "0", "-vf", f"ass={ass}", "-c:v", "libx264", "-preset", os.getenv("VIDEO_PRESET", "medium"), "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", str(output)]
    run(cmd)
