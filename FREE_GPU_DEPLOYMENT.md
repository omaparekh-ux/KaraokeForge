# KaraokeForge free GPU deployment

KaraokeForge does not need a paid AI API. The heavy worker can run temporarily on a free notebook GPU while Vercel hosts the frontend.

## Recommended: Kaggle

Kaggle currently documents free NVIDIA P100 GPU access with a weekly GPU quota around 30 hours. Open `notebooks/KaraokeForge_Kaggle_GPU.ipynb` in Kaggle, enable **GPU** and **Internet**, and run the cells from top to bottom.

The notebook:

1. clones this GitHub repository;
2. installs FFmpeg and the Python worker dependencies;
3. starts `worker/app.py` on port 8000;
4. starts a free Cloudflare Quick Tunnel;
5. prints a public `https://*.trycloudflare.com` worker URL;
6. checks `/health`.

Paste that URL into KaraokeForge's **Processing engine** field and click **Save worker**.

Cloudflare says Quick Tunnels are free and intended for development/testing. The URL is temporary and changes when the tunnel restarts.

## Fallback: Google Colab

Open `notebooks/KaraokeForge_Colab_GPU.ipynb` in Google Colab, select an available GPU runtime, and run the cells from top to bottom.

Colab's free GPU availability is dynamic. The notebook uses the same worker and the same temporary Cloudflare tunnel pattern.

## Important limitations

This setup is for a free prototype/demo. The notebook session can stop, the tunnel URL can disappear, generated files are temporary, and the worker has no always-on uptime guarantee.

For production, move the exact same `worker/` directory to a persistent GPU machine or managed GPU service and keep `JOBS_DIR` on persistent storage.

## Security for the free demo

The notebook uses `FRONTEND_ORIGINS=*` so the temporary tunnel works immediately from the browser. Anyone who knows the temporary URL can call the worker while the session is running. Do not use this configuration for sensitive media. For a controlled deployment, set `FRONTEND_ORIGINS` to the exact Vercel origin.

## Architecture

```text
Vercel Next.js
      |
      | HTTPS upload
      v
Kaggle/Colab worker
      |
      +-- FFmpeg
      +-- Demucs
      +-- faster-whisper
      +-- FFmpeg karaoke render
      |
      v
karaoke MP4 + instrumental + lyrics + ASS
```
