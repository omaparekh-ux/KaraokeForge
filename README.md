# KaraokeForge 🎤

KaraokeForge turns an uploaded song into a karaoke-ready MP4 without requiring a paid AI API.

## Pipeline

1. **FFmpeg** extracts a normalized 44.1 kHz stereo WAV.
2. **Demucs** runs `--two-stems=vocals` to produce an instrumental and isolated vocal stem.
3. **faster-whisper** transcribes the isolated vocals with word timestamps.
4. Karaoke **ASS** subtitles use `\\k` timing tags so each word highlights as it is sung.
5. **FFmpeg/libx264** renders a 1920×1080 MP4. Audio-only uploads get a clean dark background; video uploads retain the original visual track while replacing its audio with the instrumental.

Demucs documents `--two-stems=vocals` specifically for karaoke-style accompaniment extraction. citeturn0search0

## Architecture

- `app/`: Next.js frontend and API proxy, suitable for Vercel.
- `worker/`: FastAPI processing service. It must run on a machine/container that can execute FFmpeg, PyTorch, Demucs and faster-whisper.

The worker automatically uses CUDA when `WHISPER_DEVICE=auto` detects an NVIDIA-capable PyTorch runtime. Otherwise it falls back to CPU. Models are loaded once per worker process and reused between jobs.

## Run locally

### Web

```bash
npm install
npm run dev
```

Set `KARAOKEFORGE_WORKER_URL` to the worker URL.

### Worker

```bash
cd worker
python -m venv .venv
# activate the environment
pip install -r requirements.txt
ffmpeg -version
uvicorn app:app --host 0.0.0.0 --port 8000
```

For a first CPU test, use `WHISPER_MODEL=tiny` or `base`. For better lyrics, `small` is the default. A GPU worker is strongly recommended for practical processing times.

## Important production note

The current worker uses FastAPI background tasks and local disk. That is intentionally simple for the MVP. A production multi-user deployment should put jobs in a durable queue and artifacts in persistent object storage.

## Media rights

Only upload and publish media you own or have permission to use.
