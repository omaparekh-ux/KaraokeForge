# KaraokeForge 🎤

KaraokeForge turns an uploaded song into a karaoke-ready MP4 without requiring a paid AI API.

## What it does

1. **FFmpeg** extracts a normalized 44.1 kHz stereo WAV.
2. **Demucs** runs `--two-stems=vocals` to produce an instrumental and isolated vocal stem.
3. **faster-whisper** transcribes the isolated vocals with word timestamps.
4. Karaoke **ASS** subtitles use `\\k` timing tags so each word highlights as it is sung.
5. **FFmpeg/libx264** renders a 1920×1080 MP4. Audio-only uploads get a clean dark background; video uploads retain the original visual track while replacing its audio with the instrumental.

## Architecture

- `app/`: Next.js frontend. It can connect directly to a Hugging Face Gradio Space, which keeps large media uploads away from Vercel Functions.
- `worker/`: canonical FastAPI processing service with FFmpeg, Demucs, faster-whisper, SQLite job state, controlled concurrency, validation, cleanup, previews and downloads. This is the recommended self-hosted production engine.
- `hf_space/`: free Hugging Face ZeroGPU Gradio adapter for a no-paid-API prototype deployment.
- `processor/`: legacy prototype kept for reference; new development should use `worker/` or `hf_space/`.

The preferred prototype backend is configured with `NEXT_PUBLIC_KARAOKEFORGE_SPACE`, for example `your-hf-username/KaraokeForge-Worker`. The browser uses the official `@gradio/client` package to upload media and submit a queued job. Gradio Spaces expose API endpoints automatically, and the JavaScript client supports browser files plus queued status events. citeturn357765search1turn357765search3

## Local development

### Web

```bash
npm install
npm run dev
```

Copy `.env.example` to `.env.local` and set either:

```text
NEXT_PUBLIC_KARAOKEFORGE_SPACE=your-hf-username/KaraokeForge-Worker
```

or, for the self-hosted FastAPI mode:

```text
NEXT_PUBLIC_KARAOKEFORGE_WORKER_URL=http://localhost:8000
```

### Worker

```bash
cd worker
docker compose up --build
```

Or run it directly:

```bash
cd worker
python -m venv .venv
# activate the environment
pip install -r requirements.txt
ffmpeg -version
uvicorn app:app --host 0.0.0.0 --port 8000
```

### Free ZeroGPU Space

Create a new **Gradio Space**, select **ZeroGPU** hardware in the Space settings, and copy `hf_space/README.md`, `hf_space/app.py`, `hf_space/requirements.txt`, and `hf_space/packages.txt` into the Space. ZeroGPU is currently compatible with Gradio and can be hosted free on eligible personal accounts; the current free quota is 5 GPU-minutes per day. citeturn576858search0turn576858search2

The worker uses a 300-second GPU duration budget and a single concurrent queue slot. A single song can consume a meaningful part of the free daily quota, so this path is intended for prototype/testing rather than high-volume service.

## Deployment

### Vercel

Import `omaparekh-ux/KaraokeForge` into Vercel as a Next.js project. No Vercel upload proxy is required. Large media is sent directly from the browser to the configured Gradio Space or self-hosted worker.

Set:

```text
NEXT_PUBLIC_KARAOKEFORGE_SPACE=your-hf-username/KaraokeForge-Worker
```

The fallback FastAPI setting remains:

```text
NEXT_PUBLIC_KARAOKEFORGE_WORKER_URL=https://YOUR-WORKER-HOST
```

Vercel's function request-body limit is therefore not in the media-upload path. citeturn848328search1

### Self-hosted worker

Set the worker's `FRONTEND_ORIGINS` to the exact Vercel origin and keep `JOBS_DIR` on persistent storage. See `DEPLOYMENT.md` for the full configuration.

## CI

GitHub Actions validates the Next.js build and Python worker syntax on pushes and pull requests to `main`.

## Media rights

Only upload and publish media you own or have permission to use.
