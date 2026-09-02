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

Create a Hugging Face Space using the **Gradio** SDK, enable **ZeroGPU** hardware in the Space settings, and copy the contents of this directory into the Space. ZeroGPU currently requires Gradio and can be hosted free on eligible personal accounts. See the project deployment guide for the exact connection steps.
