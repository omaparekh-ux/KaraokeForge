# KaraokeForge 🎤

KaraokeForge turns an uploaded song into a karaoke-ready MP4 without requiring a paid AI API.

## What it does

1. **FFmpeg** extracts a normalized 44.1 kHz stereo WAV.
2. **Demucs** runs `--two-stems=vocals` to produce an instrumental and isolated vocal stem.
3. **faster-whisper** transcribes the isolated vocals with word timestamps.
4. Karaoke **ASS** subtitles use `\\k` timing tags so each word highlights as it is sung.
5. **FFmpeg/libx264** renders a 1920×1080 MP4. Audio-only uploads get a clean dark background; video uploads retain the original visual track while replacing its audio with the instrumental.

## Architecture

- `app/`: Next.js frontend. The browser uploads media directly to the processing worker, so large files do not pass through a Vercel Function.
- `worker/`: canonical FastAPI processing service with FFmpeg, Demucs, faster-whisper, SQLite job state, controlled concurrency, validation, cleanup, previews and downloads.
- `notebooks/`: one-click-ish free GPU launchers for Kaggle and Google Colab. They run the real `worker/` and expose it through a temporary Cloudflare Quick Tunnel.
- `hf_space/`: optional Hugging Face ZeroGPU adapter retained for accounts that are eligible to use ZeroGPU.
- `processor/`: legacy prototype kept for reference.

## Free GPU route

The recommended no-paid-compute prototype is **Kaggle GPU + Cloudflare Quick Tunnel**. Kaggle currently documents free NVIDIA P100 access with a weekly GPU quota around 30 hours. Cloudflare Quick Tunnels are free for testing/development and create a temporary HTTPS `trycloudflare.com` URL. citeturn813855search3turn813855search0

Open `notebooks/KaraokeForge_Kaggle_GPU.ipynb` in Kaggle, enable GPU and Internet, run the cells top to bottom, then copy the printed worker URL into the KaraokeForge website's **Processing engine** field.

A Google Colab version is also provided in `notebooks/KaraokeForge_Colab_GPU.ipynb`. Free Colab GPU availability is dynamic, so Kaggle is the preferred free route when available.

## Local development

### Web

```bash
npm install
npm run dev
```

Set the worker URL either with an environment variable:

```text
NEXT_PUBLIC_KARAOKEFORGE_WORKER_URL=http://localhost:8000
```

or paste an HTTPS worker URL into the website's **Processing engine** field.

### Worker

```bash
cd worker
docker compose up --build
```

Or run it directly:

```bash
cd worker
python -m venv .venv
pip install -r requirements.txt
ffmpeg -version
uvicorn app:app --host 0.0.0.0 --port 8000
```

Check `http://localhost:8000/health`.

For CPU testing, use `WHISPER_MODEL=tiny` or `base`. `small` is the default. A GPU worker is strongly recommended for useful processing times. Keep `MAX_CONCURRENT_JOBS=1` on a single-GPU machine.

## Vercel

Deploy the Next.js application to Vercel. The large upload is sent directly from the browser to the worker, avoiding the Vercel Function request-body limit. The production worker should be placed on persistent GPU/CPU infrastructure with a persistent `JOBS_DIR` volume.

## Important limitations of the free route

Kaggle/Colab notebook sessions are temporary. When the notebook stops, the worker and its temporary Cloudflare URL stop. Generated files on that session are also temporary. Quick Tunnels are explicitly intended for testing/development, not production. citeturn813855search0

## Media rights

Only upload and publish media you own or have permission to use.
