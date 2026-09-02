# KaraokeForge 🎤

KaraokeForge turns an uploaded song into a karaoke-ready MP4 without requiring a paid AI API.

## What it does

1. **FFmpeg** extracts a normalized 44.1 kHz stereo WAV.
2. **Demucs** runs `--two-stems=vocals` to produce an instrumental and isolated vocal stem.
3. **faster-whisper** transcribes the isolated vocals with word timestamps.
4. Karaoke **ASS** subtitles use `\\k` timing tags so each word highlights as it is sung.
5. **FFmpeg/libx264** renders a 1920×1080 MP4. Audio-only uploads get a clean dark background; video uploads retain the original visual track while replacing its audio with the instrumental.

## Architecture

- `app/`: Next.js frontend and API proxy for Vercel.
- `worker/`: canonical FastAPI processing service with FFmpeg, Demucs, faster-whisper, SQLite job state, controlled concurrency, validation, cleanup, previews and downloads.
- `processor/`: legacy prototype kept for reference; new development should use `worker/`.

The frontend never needs a browser-side connection to the heavy worker. It calls Next.js `/api` routes, which proxy requests to `KARAOKEFORGE_WORKER_URL`.

## Local development

### Web

```bash
npm install
npm run dev
```

Copy `.env.example` to `.env.local` and set:

```text
KARAOKEFORGE_WORKER_URL=http://localhost:8000
```

### Worker

Recommended container path:

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

Check `http://localhost:8000/health`.

For CPU testing, use `WHISPER_MODEL=tiny` or `base`. `small` is the default. A GPU worker is strongly recommended for useful processing times. Keep `MAX_CONCURRENT_JOBS=1` on a single-GPU machine.

## Deployment

Deploy the Next.js app to Vercel and set `KARAOKEFORGE_WORKER_URL` to the public HTTPS URL of the worker. The worker must run on infrastructure capable of executing FFmpeg, PyTorch, Demucs and faster-whisper. See `DEPLOYMENT.md` for the exact setup.

The worker stores job state in SQLite and generated media under `JOBS_DIR`. Use a persistent volume for production. The default cleanup policy removes completed/failed jobs after 24 hours.

## CI

GitHub Actions validates the Next.js build and Python worker syntax on pushes and pull requests to `main`.

## Media rights

Only upload and publish media you own or have permission to use.
