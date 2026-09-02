"use client";

import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";

type Status = "idle" | "uploading" | "queued" | "processing" | "complete" | "failed";
type OutputFile = { url: string; name: string };
type Job = {
  jobId: string;
  status: Status | "running" | "extracting" | "separating" | "transcribing" | "rendering";
  progress: number;
  message: string;
  filename?: string;
  error?: string;
  preview?: string;
  download?: string;
  instrumental?: string;
  lyrics?: string;
};

const stages = ["Preparing audio", "Removing vocals", "Transcribing lyrics", "Rendering video"];
const configuredWorker = process.env.NEXT_PUBLIC_KARAOKEFORGE_WORKER_URL?.trim() ?? "";
const STORAGE_KEY = "karaokeforge-worker";

function isHttpWorker(value: string) {
  return /^https:\/\//i.test(value) || /^http:\/\//i.test(value);
}

function resolveWorkerUrl(value: string, relative?: string) {
  if (!relative) return "";
  if (isHttpWorker(relative)) return relative;
  if (!value) return relative;
  return `${value.replace(/\/$/, "")}/${relative.replace(/^\//, "")}`;
}

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [worker, setWorker] = useState(configuredWorker);
  const [workerInput, setWorkerInput] = useState(configuredWorker);
  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [outputs, setOutputs] = useState<{ video: OutputFile; instrumental?: OutputFile; lyrics?: OutputFile; subtitles?: OutputFile } | null>(null);
  const [dragging, setDragging] = useState(false);
  const busy = status === "uploading" || status === "queued" || status === "processing";
  const stageIndex = useMemo(() => {
    if (status === "complete") return 4;
    if (status === "processing") return progress >= 75 ? 3 : progress >= 50 ? 2 : progress >= 20 ? 1 : 0;
    return 0;
  }, [progress, status]);

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved) {
      setWorker(saved);
      setWorkerInput(saved);
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
    setJobId("");
    setJob(null);
    setOutputs(null);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (!busy) choose(event.dataTransfer.files?.[0]);
  }

  function saveWorker() {
    const value = workerInput.trim().replace(/\/$/, "");
    if (!value) {
      setError("Enter the HTTPS URL of your running KaraokeForge worker.");
      return;
    }
    if (!isHttpWorker(value)) {
      setError("Worker URL must start with http:// or https://.");
      return;
    }
    setWorker(value);
    window.localStorage.setItem(STORAGE_KEY, value);
    setError("");
    setMessage("Worker saved.");
  }

  useEffect(() => {
    if (!jobId || !worker || status === "complete" || status === "failed") return;
    let cancelled = false;
    const poll = async () => {
      try {
        const response = await fetch(`${worker}/jobs/${jobId}`, { cache: "no-store" });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Could not read job status.");
        if (cancelled) return;
        const nextStatus = data.status === "complete" ? "complete" : data.status === "failed" ? "failed" : "processing";
        setJob(data);
        setProgress(Math.max(0, Math.min(100, Number(data.progress || 0))));
        setMessage(data.message || "Processing…");
        setStatus(nextStatus);
        if (data.status === "failed") setError(data.error || "Processing failed.");
        if (data.status === "complete") {
          setOutputs({
            video: { url: resolveWorkerUrl(worker, data.download || data.preview), name: "karaokeforge.mp4" },
            instrumental: data.instrumental ? { url: resolveWorkerUrl(worker, data.instrumental), name: "instrumental.wav" } : undefined,
            lyrics: data.lyrics ? { url: resolveWorkerUrl(worker, data.lyrics), name: "lyrics.json" } : undefined,
            subtitles: data.subtitles ? { url: resolveWorkerUrl(worker, data.subtitles), name: "lyrics.ass" } : undefined,
          });
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Status check failed.");
      }
    };
    poll();
    const timer = window.setInterval(poll, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [jobId, status, worker]);

  async function start() {
    if (!file || busy) return;
    const target = worker.trim().replace(/\/$/, "");
    if (!target) {
      setError("Connect a worker first.");
      return;
    }
    if (!isHttpWorker(target)) {
      setError("Worker URL must start with http:// or https://.");
      return;
    }
    setError("");
    setOutputs(null);
    setJob(null);
    setJobId("");
    setStatus("uploading");
    setProgress(3);
    setMessage("Uploading media to the GPU worker…");
    try {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch(`${target}/jobs`, { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Upload failed.");
      setJobId(data.jobId);
      setJob(data);
      setStatus("queued");
      setProgress(7);
      setMessage("Queued for processing…");
    } catch (err) {
      setStatus("failed");
      setError(err instanceof Error ? err.message : "Upload failed.");
      setMessage("");
    }
  }

  function reset() {
    setFile(null);
    setStatus("idle");
    setProgress(0);
    setMessage("");
    setError("");
    setJobId("");
    setJob(null);
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
      {busy && <div className="statusPanel"><div className="statusTop"><div><b>{message || "Processing"}</b><span>{job?.filename || file?.name}</span></div><strong>{progress}%</strong></div><div className="bar"><div style={{ width: `${progress}%` }}/></div><div className="steps">{stages.map((stageName, index) => <div key={stageName} className={index < stageIndex || (index === stageIndex && progress >= [15, 40, 65, 88][index]) ? "step active" : "step"}><span>{index < stageIndex ? "✓" : index + 1}</span>{stageName}</div>)}</div></div>}
      {error && <div className="error">{error}</div>}{status === "failed" && <button className="secondary wide" onClick={() => { setStatus("idle"); setError(""); }}>Try again</button>}
    </section> : <section className="result"><div className="resultHeader"><div><div className="eyebrow">✓ Karaoke ready</div><h2>{file?.name || "Your karaoke video"}</h2><p>Word-timed lyrics and instrumental track included.</p></div><button className="secondary" onClick={reset}>Create another</button></div><div className="player"><video controls playsInline src={outputs.video.url}/></div><div className="actions"><a className="primary action" href={outputs.video.url} download>Download karaoke MP4</a>{outputs.instrumental && <a className="secondary action" href={outputs.instrumental.url} download>Download instrumental</a>}{outputs.lyrics && <a className="secondary action" href={outputs.lyrics.url} download>Download lyrics JSON</a>}{outputs.subtitles && <a className="secondary action" href={outputs.subtitles.url} download>Download subtitles</a>}</div></section>}

    <section className="workerConfig"><div><b>Processing engine</b><span>Paste the HTTPS URL from your Kaggle or Colab worker.</span></div><div className="workerRow"><input value={workerInput} onChange={(event) => setWorkerInput(event.target.value)} placeholder="https://your-worker.trycloudflare.com" aria-label="KaraokeForge worker URL"/><button className="secondary" onClick={saveWorker}>Save worker</button></div>{worker && <div className="connected">● Connected to <strong>{worker}</strong></div>}</section>
    <section className="features"><div className="feature"><b>🎚 Clean instrumental</b><span>Demucs separates vocals from the accompaniment without a paid AI API.</span></div><div className="feature"><b>📝 Word-synced lyrics</b><span>Whisper timestamps individual words so the karaoke highlight follows the singer.</span></div><div className="feature"><b>🎬 YouTube-ready render</b><span>1080p H.264 video with AAC audio and burned-in karaoke subtitles.</span></div></section><div className="footer">Only upload media you own or have permission to process and publish.</div>
  </main>;
}
