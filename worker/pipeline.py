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
    run(["python", "-m", "demucs", "--two-stems=vocals", "-n", os.getenv("DEMUCS_MODEL", "htdemucs"), "-o", str(out_dir), str(audio)])
    candidates = list(out_dir.glob("**/no_vocals.wav"))
    if not candidates:
        raise FileNotFoundError("Demucs did not produce no_vocals.wav")
    return candidates[0]


def transcribe(vocal_audio: Path) -> list[dict[str, Any]]:
    from faster_whisper import WhisperModel

    model = WhisperModel(os.getenv("WHISPER_MODEL", "small"), device=os.getenv("WHISPER_DEVICE", "cpu"), compute_type=os.getenv("WHISPER_COMPUTE", "int8"))
    segments, _ = model.transcribe(str(vocal_audio), word_timestamps=True, vad_filter=True)
    result: list[dict[str, Any]] = []
    for segment in segments:
        words = []
        for word in segment.words or []:
            words.append({"text": word.word.strip(), "start": word.start, "end": word.end})
        result.append({"text": segment.text.strip(), "start": segment.start, "end": segment.end, "words": words})
    return result


def ass_time(seconds: float) -> str:
    cs = int(round(seconds * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def escape_ass(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", " ")


def make_ass(segments: list[dict[str, Any]], target: Path) -> None:
    lines = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080", "",
        "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Karaoke,Arial,64,&H00FFFFFF,&H00FFFFFF,&H00111111,&H66000000,-1,0,0,0,100,100,0,0,1,3,1,2,100,100,90,1", "",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for seg in segments:
        words = seg.get("words") or []
        text = " ".join(w["text"] for w in words) if words else seg["text"]
        lines.append(f"Dialogue: 0,{ass_time(seg['start'])},{ass_time(seg['end'])},Karaoke,,0,0,0,,{escape_ass(text)}")
    target.write_text("\n".join(lines), encoding="utf-8")


def render_video(instrumental: Path, source: Path, ass: Path, output: Path) -> None:
    # Keep original video when present; otherwise create a simple dark background.
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_type", "-of", "json", str(source)], capture_output=True, text=True)
    has_video = bool(json.loads(probe.stdout or "{}" ).get("streams"))
    if has_video:
        cmd = ["ffmpeg", "-y", "-i", str(source), "-i", str(instrumental), "-map", "0:v:0", "-map", "1:a:0", "-vf", f"ass={ass}", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-c:a", "aac", "-b:a", "256k", "-shortest", str(output)]
    else:
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1920x1080:r=30", "-i", str(instrumental), "-vf", f"ass={ass}", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "256k", "-shortest", str(output)]
    run(cmd)
