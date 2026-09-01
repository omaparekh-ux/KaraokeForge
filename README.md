# KaraokeForge

KaraokeForge is an open-source karaoke video generator. The web app accepts audio/video uploads and is designed to produce a vocal-reduced instrumental track, synchronized lyrics, and a YouTube-ready MP4.

## Architecture

- **Web:** Next.js + TypeScript, deployable to Vercel.
- **Processing:** Python worker using PyTorch, Demucs/future source-separation models, faster-whisper, and FFmpeg.
- **No paid AI API required:** the core ML pipeline is designed around open-source models.
- **Deployment:** keep heavy processing outside Vercel serverless functions; connect a dedicated CPU/GPU worker for production processing.

## Planned processing pipeline

1. Upload and validate MP3/WAV/M4A/MP4/MOV.
2. Extract audio with FFmpeg.
3. Separate vocals and instrumental with Demucs.
4. Transcribe vocals with faster-whisper.
5. Align lyrics and generate SRT/ASS karaoke timing.
6. Render lyric overlays and instrumental audio into an MP4.
7. Store the finished artifact and expose it for download.

## Development

```bash
npm install
npm run dev
```

The current web MVP contains the polished upload interface. The processing worker will be added as the next layer so the frontend remains lightweight.
