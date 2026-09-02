# KaraokeForge 🎤

KaraokeForge turns an uploaded song into a karaoke-ready MP4 without requiring a paid AI API.

## What it does

1. **FFmpeg** extracts a normalized 44.1 kHz stereo WAV.
2. **Demucs** runs `--two-stems=vocals` to produce an instrumental and isolated vocal stem.
3. **faster-whisper** transcribes the isolated vocals with word timestamps.
4. Karaoke **ASS** subtitles use `\\k` timing tags so each word highlights as it is sung.
5. **FFmpeg/libx264** renders a 1920×1080 MP4. Audio-only uploads get a clean dark background; video uploads retain the original visual track while replacing its audio with the instrumental.

## Architecture

- `app/`: Next.js frontend. Large media is uploaded directly from the browser to the worker.
- `worker/`: canonical FastAPI processing service with FFmpeg, Demucs, faster-whisper, SQLite job state, controlled concurrency, validation, cleanup, previews and downloads.
- `processor/`: legacy prototype kept for reference; new development should use `worker/`.

The public worker URL is exposed to the browser through `NEXT_PUBLIC_KARAOKEFORGE_WORKER_URL`. The worker enables CORS only for the origins listed in `FRONTEND_ORIGINS`.

## Local development

### Web

```bash
npm install
npm run dev
```

Copy `.env.example` to `.env.local` and set:

```text
NEXT_PUBLIC_KARAOKEFORGE_WORKER_URL=http://localhost:8000
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

Import the repository into Vercel as a Next.js project. Set `NEXT_PUBLIC_KARAOKEFORGE_WORKER_URL` to the public HTTPS URL of the worker. Also set the same URL in `KARAOKEFORGE_WORKER_URL` when server-side proxy routes are needed.

The browser uploads the actual media directly to the worker. This avoids Vercel Functions' 4.5 MB request payload limit, which is too small for many songs and practically all source videos. citeturn848328search1

On the worker, set:

```text
FRONTEND_ORIGINS=https://your-vercel-domain.vercel.app
```

The worker must run on infrastructure capable of executing FFmpeg, PyTorch, Demucs and faster-whisper. Use a persistent volume for `JOBS_DIR` so generated media and the SQLite job database survive restarts. See `DEPLOYMENT.md` for the full setup.

## CI

GitHub Actions validates the Next.js build and Python worker syntax on pushes and pull requests to `main`.

## Media rights

Only upload and publish media you own or have permission to use.
