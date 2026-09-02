# KaraokeForge deployment

## 1. Web app on Vercel

Import `omaparekh-ux/KaraokeForge` into Vercel as a Next.js project.

Set this public environment variable in Vercel:

```text
NEXT_PUBLIC_KARAOKEFORGE_WORKER_URL=https://YOUR-WORKER-HOST
```

The browser uploads media directly to the karaoke worker. This is intentional: Vercel Functions currently enforce a 4.5 MB request payload limit, while songs and videos are commonly much larger. citeturn848328search1

Keep this optional server-side variable for the API proxy routes:

```text
KARAOKEFORGE_WORKER_URL=https://YOUR-WORKER-HOST
```

## 2. Worker container

The canonical processing engine is the `worker/` directory. It contains FFmpeg, Demucs, faster-whisper, SQLite job state, controlled concurrency, validation, cleanup, preview and download endpoints.

For a local or self-hosted worker:

```bash
cd worker
docker compose up --build
```

Then check:

```text
http://localhost:8000/health
```

For local development, `FRONTEND_ORIGINS=http://localhost:3000` is already configured in `docker-compose.yml`. In production, set it to the exact HTTPS origin of your Vercel app, for example:

```text
FRONTEND_ORIGINS=https://karaokeforge.vercel.app
```

The worker needs enough CPU/RAM for PyTorch and benefits substantially from an NVIDIA GPU. Models are downloaded lazily on first use. Keep `MAX_CONCURRENT_JOBS=1` on a single-GPU machine.

## 3. Connect the two

Run the worker on a public HTTPS endpoint. Put that URL into both Vercel variables above, and set the same Vercel origin in `FRONTEND_ORIGINS` on the worker.

The user flow is:

```text
Browser → Worker upload → Queue → Demucs → Whisper → FFmpeg → Worker output
   ↑                                                              │
   └────────────── status / preview / download ──────────────────┘
```

Vercel only serves the Next.js application and its lightweight API routes. Large media never has to pass through the Vercel Function payload limit. citeturn848328search1

## 4. Production storage

Use a persistent volume for `JOBS_DIR`, because generated MP4s, WAV stems, lyrics and the SQLite job database live there. The worker's cleanup policy removes completed/failed jobs after the configured TTL, 24 hours by default.

## Important

Only process media you own or have permission to use.
