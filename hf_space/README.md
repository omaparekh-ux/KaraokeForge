---
title: KaraokeForge Worker
emoji: 🎤
colorFrom: purple
colorTo: indigo
sdk: gradio
sdk_version: 6.26.0
app_file: app.py
python_version: 3.10
---

# KaraokeForge ZeroGPU Worker

This Space is the free GPU-backed processing adapter for KaraokeForge.

It accepts an audio or video file and returns:

- a 1920×1080 karaoke MP4
- the vocal-free instrumental WAV
- timestamped lyrics JSON
- the generated ASS subtitle file

The GPU work is performed with open-source Demucs and faster-whisper. No paid AI API is required.

## Setup

Create a Hugging Face Space using the **Gradio** SDK, enable **ZeroGPU** hardware in the Space settings, and copy the contents of this directory into the Space. ZeroGPU currently requires Gradio and can be hosted free on eligible personal accounts. Free accounts currently receive 5 GPU-minutes per day. citeturn614643search0

The karaoke callback requests up to 120 seconds of GPU execution, which is intentionally bounded for the free tier. A normal full-length song can still exceed that budget depending on model loading and render time. The scalable FastAPI worker in `worker/` is the production path when longer jobs are needed.
