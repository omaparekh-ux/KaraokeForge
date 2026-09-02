from __future__ import annotations
import json,os,subprocess
from pathlib import Path
from typing import Any

def run(cmd:list[str])->None:
    p=subprocess.run(cmd,check=False,text=True,capture_output=True)
    if p.returncode!=0:
        detail=(p.stderr or p.stdout or "unknown processing error").strip(); raise RuntimeError(f"Command failed ({p.returncode}): {detail[-1600:]}")
def _device()->str:
    wanted=os.getenv("DEMUCS_DEVICE","auto")
    if wanted!="auto":return wanted
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:return "cpu"
def extract_audio(source:Path,wav:Path)->None:run(["ffmpeg","-y","-i",str(source),"-vn","-ac","2","-ar","44100","-c:a","pcm_s16le",str(wav)])
def separate_vocals(audio:Path,out_dir:Path)->Path:
    cmd=["python","-m","demucs","--two-stems=vocals","-n",os.getenv("DEMUCS_MODEL","htdemucs"),"-d",_device(),"-o",str(out_dir),str(audio)]; segment=os.getenv("DEMUCS_SEGMENT")
    if segment:cmd.extend(["--segment",segment])
    run(cmd); candidates=list(out_dir.glob("**/no_vocals.wav"))
    if not candidates:raise FileNotFoundError("Demucs did not produce no_vocals.wav")
    return candidates[0]
_MODEL=None
def _whisper_model():
    from faster_whisper import WhisperModel
    device=os.getenv("WHISPER_DEVICE","auto")
    if device=="auto":
        try:
            import torch; device="cuda" if torch.cuda.is_available() else "cpu"
        except Exception:device="cpu"
    compute=os.getenv("WHISPER_COMPUTE","float16" if device=="cuda" else "int8")
    return WhisperModel(os.getenv("WHISPER_MODEL","small"),device=device,compute_type=compute)
def transcribe(vocal_audio:Path)->list[dict[str,Any]]:
    global _MODEL
    if _MODEL is None:_MODEL=_whisper_model()
    language=os.getenv("WHISPER_LANGUAGE") or None; segments,_=_MODEL.transcribe(str(vocal_audio),word_timestamps=True,vad_filter=True,beam_size=5,language=language,condition_on_previous_text=True); result=[]
    for segment in segments:
        words=[]
        for word in segment.words or []:
            if word.start is None or word.end is None:continue
            text=word.word.strip()
            if text:words.append({"text":text,"start":float(word.start),"end":float(word.end)})
        text=" ".join(w["text"] for w in words).strip() or segment.text.strip()
        if text:result.append({"text":text,"start":float(segment.start),"end":float(segment.end),"words":words})
    return result
def ass_time(seconds:float)->str:
    total=max(0,int(round(seconds*100))); h,rest=divmod(total,360000); m,rest=divmod(rest,6000); s,cs=divmod(rest,100); return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
def escape_ass(text:str)->str:return text.replace("\\","\\\\").replace("{","\\{").replace("}","\\}").replace("\n"," ").strip()
def _wrap_words(words:list[dict[str,Any]],max_chars:int=42)->list[list[dict[str,Any]]]:
    lines=[]; current=[]; size=0
    for word in words:
        extra=len(word["text"])+(1 if current else 0)
        if current and size+extra>max_chars:lines.append(current);current=[];size=0
        current.append(word);size+=extra
    if current:lines.append(current)
    return lines
def make_ass(segments:list[dict[str,Any]],target:Path)->None:
    lines=["[Script Info]","ScriptType: v4.00+","PlayResX: 1920","PlayResY: 1080","WrapStyle: 2","ScaledBorderAndShadow: yes","","[V4+ Styles]","Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding","Style: Karaoke,DejaVu Sans,64,&H0000D7FF,&H00FFFFFF,&H00101010,&H99000000,-1,0,0,0,100,100,0,0,1,4,2,2,120,120,100,1","","[Events]","Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for segment in segments:
        words=segment.get("words") or []
        if not words:
            lines.append(f"Dialogue: 0,{ass_time(segment['start'])},{ass_time(segment['end'])},Karaoke,,0,0,0,,{escape_ass(segment.get('text',''))}");continue
        for line_words in _wrap_words(words):
            chunks=[f"{{\\k{max(1,int(round((w['end']-w['start'])*100)))}}}{escape_ass(w['text'])}" for w in line_words]; payload=" ".join(chunks); lines.append(f"Dialogue: 0,{ass_time(line_words[0]['start'])},{ass_time(line_words[-1]['end'])},Karaoke,,0,0,0,,{payload}")
    target.write_text("\n".join(lines),encoding="utf-8")
def _has_video(source:Path)->bool:
    p=subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=codec_type","-of","json",str(source)],capture_output=True,text=True,check=False)
    try:return bool(json.loads(p.stdout or "{}").get("streams"))
    except json.JSONDecodeError:return False
def _duration(source:Path)->str:
    p=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",str(source)],capture_output=True,text=True,check=False); return p.stdout.strip()
def render_video(instrumental:Path,source:Path,ass:Path,output:Path)->None:
    preset=os.getenv("VIDEO_PRESET","medium")
    if _has_video(source):cmd=["ffmpeg","-y","-i",str(source),"-i",str(instrumental),"-map","0:v:0","-map","1:a:0","-vf",f"ass={ass}","-c:v","libx264","-preset",preset,"-crf","19","-pix_fmt","yuv420p","-c:a","aac","-b:a","256k","-shortest","-movflags","+faststart",str(output)]
    else:
        duration=_duration(instrumental); cmd=["ffmpeg","-y","-f","lavfi","-i","color=c=0x09090b:s=1920x1080:r=30","-i",str(instrumental),"-t",duration or "0","-vf",f"ass={ass}","-c:v","libx264","-preset",preset,"-crf","20","-pix_fmt","yuv420p","-c:a","aac","-b:a","256k","-shortest","-movflags","+faststart",str(output)]
    run(cmd)
