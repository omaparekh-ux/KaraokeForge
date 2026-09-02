"use client";

import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";
import { Client, handle_file } from "@gradio/client";

type Status = "idle" | "uploading" | "queued" | "processing" | "complete" | "failed";
type OutputFile = { url: string; name: string };

const stages = ["Preparing audio", "Removing vocals", "Transcribing lyrics", "Rendering video"];
const configuredSpace = process.env.NEXT_PUBLIC_KARAOKEFORGE_SPACE?.trim() ?? "";
const STORAGE_KEY = "karaokeforge-space";

function fileUrl(value: unknown): OutputFile | null {
  if (typeof value === "string") return { url: value, name: "download" };
  if (!value || typeof value !== "object") return null;
  const item = value as { url?: string; path?: string; orig_name?: string };
  if (item.url) return { url: item.url, name: item.orig_name || "download" };
  if (item.path && /^https?:\/\//.test(item.path)) return { url: item.path, name: item.orig_name || "download" };
  return null;
}

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [space, setSpace] = useState(configuredSpace);
  const [spaceInput, setSpaceInput] = useState(configuredSpace);
  const [outputs, setOutputs] = useState<{ video: OutputFile; instrumental?: OutputFile; lyrics?: OutputFile; subtitles?: OutputFile } | null>(null);
  const [dragging, setDragging] = useState(false);
  const busy = status === "uploading" || status === "queued" || status === "processing";
  const stageIndex = useMemo(() => {
    if (status === "complete") return 4;
    if (status === "processing") return progress >= 75 ? 3 : progress >= 50 ? 2 : progress >= 20 ? 1 : 0;
    if (status === "queued") return 0;
    if (status === "uploading") return 0;
    return 0;
  }, [progress, status]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved) {
      setSpace(saved);
      setSpaceInput(saved);
    }
  }, []);

  function choose(selected?: File) {
    if (!selected) return;
    const valid = selected.type.startsWith("audio/") || selected.type.startsWith("video/") || /\.(mp3|wav|m4a|aac|flac|ogg|mp4|mov|mkv|webm)$/i.test(selected.name);
    if (!valid) {
      setError("Please choose an audio or video file.");
      return;
    }
    setFile(selected);
    setStatus("idle");
    setProgress(0);
    setMessage("");
    setError("");
    setOutputs(null);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (!busy) choose(event.dataTransfer.files?.[0]);
  }

  function saveSpace() {
    const value = spaceInput.trim();
    if (!value) {
      setError("Enter your Hugging Face Space, such as username/KaraokeForge-Worker.");
      return;
    }
    setSpace(value);
    window.localStorage.setItem(STORAGE_KEY, value);
    setError("");
    setMessage("Worker Space saved.");
  }

  async function start() {
    if (!file || busy) return;
    const target = space.trim();
    if (!target) {
      setError("Connect the Hugging Face Worker Space first.");
      return;
    }
    setError("");
    setOutputs(null);
    setStatus("uploading");
    setProgress(3);
    setMessage("Connecting to the GPU worker…");

    try {
      const app = await Client.connect(target, { events: ["status", "data"] });
      setStatus("queued");
      setProgress(7);
      setMessage("Queued for GPU processing…");

      const job = app.submit("/forge", [handle_file(file)]);
      let resultData: unknown[] | null = null;

      for await (const event of job as AsyncIterable<any>) {
        if (event?.type === "status") {
          const desc = event?.progress_data?.[0]?.desc || event?.message || "Processing…";
          const raw = event?.progress_data?.[0]?.progress;
          const current = typeof raw === "number" ? Math.round(raw * 100) : undefined;
          if (event?.stage === "error" || event?.success === false) throw new Error(event?.message || "GPU processing failed.");
          if (current !== undefined) setProgress(Math.max(8, Math.min(95, current)));
          setMessage(desc);
          setStatus(event?.stage === "pending" ? "queued" : "processing");
        }
        if (event?.type === "data" && Array.isArray(event.data)) {
          resultData = event.data;
        }
      }

      if (!resultData) throw new Error("The worker finished without returning files.");
      const video = fileUrl(resultData[0]);
      if (!video?.url) throw new Error("The worker did not return the karaoke MP4.");
      setOutputs({ video, instrumental: fileUrl(resultData[1]) ?? undefined, lyrics: fileUrl(resultData[2]) ?? undefined, subtitles: fileUrl(resultData[3]) ?? undefined });
      setProgress(100);
      setMessage("Karaoke ready.");
      setStatus("complete");
    } catch (err) {
      setStatus("failed");
      setError(err instanceof Error ? err.message : "Processing failed.");
      setMessage("");
    }
  }

  function reset() {
    setFile(null);
    setStatus("idle");
    setProgress(0);
    setMessage("");
    setError("");
    setOutputs(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  return <main className="shell">
    <nav className="nav"><div className="brand">Karaoke<span>Forge</span></div><div className="badge">Open-source audio pipeline</div></nav>
    <section className="hero"><div className="eyebrow">🎤 Karaoke studio</div><h1>Turn a song into <em>karaoke.</em></h1><p>Upload your audio or video. KaraokeForge removes the lead vocal, creates word-timed lyrics, and renders a YouTube-ready MP4.</p></section>

    {!outputs ? <section className="card">
      <div onClick={() => !busy && inputRef.current?.click()} onDragOver={(event) => { event.preventDefault(); if (!busy) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop} className={`drop ${dragging ? "dragging" : ""}`}>
        <input ref={inputRef} className="hidden" type="file" accept="audio/*,video/*,.mp3,.wav,.m4a,.aac,.flac,.ogg,.mp4,.mov,.mkv,.webm" onChange={(event: ChangeEvent<HTMLInputElement>) => choose(event.target.files?.[0])}/><div className="icon">{busy ? "◌" : "↑"}</div><h2>{file ? file.name : "Drop your song here"}</h2><p>{file ? `${(file.size / 1024 / 1024).toFixed(1)} MB · ready to forge` : "Audio or video. We’ll handle the rest."}</p>
        {!busy && <button className="primary" onClick={(event) => { event.stopPropagation(); inputRef.current?.click(); }}>{file ? "Choose another file" : "Choose a file"}</button>}{!busy && file && <button className="secondary" onClick={(event) => { event.stopPropagation(); start(); }}>Create karaoke video</button>}<div className="formats">MP3 · WAV · M4A · FLAC · MP4 · MOV · MKV · WEBM</div>
      </div>
      {busy && <div className="statusPanel"><div className="statusTop"><div><b>{message || "Processing"}</b><span>{file?.name}</span></div><strong>{progress}%</strong></div><div className="bar"><div style={{ width: `${progress}%` }}/></div><div className="steps">{stages.map((stageName, index) => <div key={stageName} className={index < stageIndex || (index === stageIndex && progress >= [15, 40, 65, 88][index]) ? "step active" : "step"}><span>{index < stageIndex ? "✓" : index + 1}</span>{stageName}</div>)}</div></div>}
      {error && <div className="error">{error}</div>}{status === "failed" && <button className="secondary wide" onClick={() => { setStatus("idle"); setError(""); }}>Try again</button>}
    </section> : <section className="result"><div className="resultHeader"><div><div className="eyebrow">✓ Karaoke ready</div><h2>{file?.name || "Your karaoke video"}</h2><p>Word-timed lyrics and instrumental track included.</p></div><button className="secondary" onClick={reset}>Create another</button></div><div className="player"><video controls playsInline src={outputs.video.url}/></div><div className="actions"><a className="primary action" href={outputs.video.url} download>Download karaoke MP4</a>{outputs.instrumental && <a className="secondary action" href={outputs.instrumental.url} download>Download instrumental</a>}{outputs.lyrics && <a className="secondary action" href={outputs.lyrics.url} download>Download lyrics JSON</a>}{outputs.subtitles && <a className="secondary action" href={outputs.subtitles.url} download>Download subtitles</a>}</div></section>}

    <section className="workerConfig"><div><b>Processing engine</b><span>Connect your free Hugging Face ZeroGPU Space once.</span></div><div className="workerRow"><input value={spaceInput} onChange={(event) => setSpaceInput(event.target.value)} placeholder="username/KaraokeForge-Worker" aria-label="Hugging Face Space"/><button className="secondary" onClick={saveSpace}>Save worker</button></div>{space && <div className="connected">● Connected to <strong>{space}</strong></div>}</section>
    <section className="features"><div className="feature"><b>🎚 Clean instrumental</b><span>Demucs separates vocals from the accompaniment without a paid AI API.</span></div><div className="feature"><b>📝 Word-synced lyrics</b><span>Whisper timestamps individual words so the karaoke highlight follows the singer.</span></div><div className="feature"><b>🎬 YouTube-ready render</b><span>1080p H.264 video with AAC audio and burned-in karaoke subtitles.</span></div></section><div className="footer">Only upload media you own or have permission to process and publish.</div>
  </main>;
}
