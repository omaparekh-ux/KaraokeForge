# KaraokeForge deployment

KaraokeForge has two backend modes:

1. **Free prototype:** Hugging Face ZeroGPU + Gradio. This is the recommended no-paid-API route.
2. **Scalable production:** the existing FastAPI worker in `worker/`, hosted on a persistent GPU/CPU machine.

## 1. Vercel web app

Import `omaparekh-ux/KaraokeForge` into Vercel as a Next.js project.

Set the preferred backend as:

```text
NEXT_PUBLIC_KARAOKEFORGE_SPACE=your-hf-username/KaraokeForge-Worker
```

The frontend also lets you save the Space ID in the browser, so the deployment can work without rebuilding after you create the Space.

Large media is uploaded from the browser directly to the processing backend, not through a Vercel Function. This avoids Vercel's request-body limit on the media path. citeturn848328search1

## 2. Free Hugging Face ZeroGPU backend

Create a new Hugging Face Space using the **Gradio** SDK. In the Space settings, select **ZeroGPU** hardware. Free personal accounts that meet Hugging Face's current eligibility requirements can host up to two ZeroGPU Spaces for free. The current free account quota is 5 GPU-minutes per day, and ZeroGPU currently requires Gradio. citeturn576858search0turn576858search2

Copy these files from `hf_space/` into the new Space root:

```text
README.md
app.py
requirements.txt
packages.txt
```

The Space exposes the `forge` Gradio endpoint automatically. The frontend uses `@gradio/client` to upload the browser's file and submit a queued job. Gradio's current client supports browser `File`/`Blob` inputs, `submit()`, and status events. citeturn344325search0turn357765search1

The ZeroGPU worker performs:

```text
upload
  ↓
FFmpeg audio normalization
  ↓
Demucs vocal separation
  ↓
faster-whisper word timestamps
  ↓
ASS karaoke timing
  ↓
FFmpeg 1920×1080 render
  ↓
MP4 + WAV + JSON + ASS
```

The worker requests up to five minutes of GPU time for a job. Because the free quota is only 5 GPU-minutes per day, this mode is suitable for development/testing and low-volume use, not a public high-volume service. citeturn576858search0

## 3. Connect Vercel to the Space

Put the Space ID in Vercel as `NEXT_PUBLIC_KARAOKEFORGE_SPACE`, or enter the same value once in the app's **Processing engine** field.

Example:

```text
omaparekh/KaraokeForge-Worker
```

No Hugging Face token is needed for a public Space.

## 4. Scalable self-hosted backend

For production scale, use `worker/` instead of the ZeroGPU adapter. The worker is a FastAPI service with SQLite job state, controlled concurrency, cleanup, preview and download endpoints.

Run locally:

```bash
cd worker
docker compose up --build
```

Use a persistent volume for `/app/jobs`. On a single GPU machine, keep:

```text
MAX_CONCURRENT_JOBS=1
```

Set:

```text
FRONTEND_ORIGINS=https://your-vercel-domain.vercel.app
```

and use:

```text
NEXT_PUBLIC_KARAOKEFORGE_WORKER_URL=https://your-worker-host
```

The self-hosted worker is the better long-term architecture because it is not limited by a daily shared GPU quota.

## 5. First end-to-end test

After the Space is running:

1. Open the Vercel app.
2. Enter the Space ID in **Processing engine** if it was not set as a Vercel environment variable.
3. Upload an MP3 or MP4.
4. Press **Create karaoke video**.
5. Wait for the Gradio queue to complete.
6. Verify the preview, MP4, instrumental WAV, lyrics JSON and ASS files.

Only process media you own or have permission to process and publish.
