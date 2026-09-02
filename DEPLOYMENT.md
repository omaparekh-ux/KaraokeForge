# KaraokeForge deployment

## 1. Web app on Vercel

Import the GitHub repository `omaparekh-ux/KaraokeForge` into Vercel as a Next.js project.

Set this environment variable in Vercel:

```text
KARAOKEFORGE_WORKER_URL=https://YOUR-WORKER-HOST
```

The browser never talks directly to the worker. Next.js proxies uploads, job status, previews, lyrics, and downloads through `/api` routes.

## 2. Worker container

The canonical processing engine is the `worker/` directory. It contains FFmpeg, Demucs, faster-whisper, SQLite-backed job state, controlled concurrency, validation, cleanup, preview, and artifact endpoints.

For a local or self-hosted worker:

```bash
cd worker
docker compose up --build
```

Then check:

```text
http://localhost:8000/health
```

The worker needs enough CPU/RAM for PyTorch and benefits substantially from an NVIDIA GPU. Models are downloaded lazily on first use. Keep `MAX_CONCURRENT_JOBS=1` on a single-GPU machine.

## 3. Connect the two

Run the worker on a public HTTPS endpoint, then set `KARAOKEFORGE_WORKER_URL` in the Vercel project to that endpoint and redeploy the web app.

## Important

Vercel is the web layer, not the Demucs/Whisper compute layer. Do not put the heavy worker inside a normal Vercel serverless function.

Only process media you own or have permission to use.
