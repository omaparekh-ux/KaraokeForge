"use client";

import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";

type Status = "idle" | "queued" | "running" | "uploading" | "extracting" | "separating" | "transcribing" | "rendering" | "complete" | "failed";
type Job = { jobId: string; status: Status; progress: number; message: string; filename?: string; error?: string; wordCount?: number; segmentCount?: number };

const stages = ["Preparing audio", "Removing vocals", "Transcribing lyrics", "Rendering video"];

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");

  const busy = !!job && !["complete", "failed"].includes(job.status);
  const percent = Math.max(0, Math.min(100, job?.progress ?? 0));
  const stageIndex = useMemo(() => ({ queued: 0, running: 0, extracting: 0, separating: 1, transcribing: 2, rendering: 3, complete: 4 } as Record<string, number>)[job?.status ?? "queued"] ?? 0, [job?.status]);

  function choose(selected?: File) {
    if (!selected) return;
    if (!(selected.type.startsWith("audio/") || selected.type.startsWith("video/"))) {
      setError("Please choose an audio or video file.");
      return;
    }
    setFile(selected); setJob(null); setError("");
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault(); setDragging(false); choose(event.dataTransfer.files?.[0]);
  }

  useEffect(() => {
    if (!job?.jobId || ["complete", "failed"].includes(job.status)) return;
    const poll = async () => {
      try {
        const response = await fetch(`/api/jobs/${job.jobId}`, { cache: "no-store" });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Could not read job status.");
        setJob(data);
        if (data.status === "failed") setError(data.error || "Processing failed.");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Status check failed.");
      }
    };
    poll();
    const timer = window.setInterval(poll, 1500);
    return () => window.clearInterval(timer);
  }, [job?.jobId, job?.status]);

  async function start() {
    if (!file || busy) return;
    setError(""); setJob({ jobId: "", status: "uploading", progress: 0, message: "Uploading media…", filename: file.name });
    const body = new FormData(); body.append("file", file);
    try {
      const response = await fetch("/api/jobs", { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Upload failed.");
      setJob({ ...data, progress: 0, message: "Queued" });
    } catch (err) {
      setJob({ jobId: "", status: "failed", progress: 0, message: "", filename: file.name });
      setError(err instanceof Error ? err.message : "Upload failed.");
    }
  }

  function reset() {
    setFile(null); setJob(null); setError("");
    if (inputRef.current) inputRef.current.value = "";
  }

  const previewUrl = job?.jobId ? `/api/jobs/${job.jobId}/preview` : "";
  const downloadUrl = job?.jobId ? `/api/jobs/${job.jobId}/download` : "";

  return <main className="shell">
    <nav className="nav"><div className="brand">Karaoke<span>Forge</span></div><div className="badge">Open-source audio pipeline</div></nav>
    <section className="hero"><div className="eyebrow">🎤 Karaoke studio</div><h1>Turn a song into <em>karaoke.</em></h1><p>Upload your audio or video. KaraokeForge removes the lead vocal, creates word-timed lyrics, and renders a YouTube-ready MP4.</p></section>

    {!job || job.status !== "complete" ? <section className="card">
      <div onClick={() => !busy && inputRef.current?.click()} onDragOver={(event) => { event.preventDefault(); if (!busy) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop} className={`drop ${dragging ? "dragging" : ""}`}>
        <input ref={inputRef} className="hidden" type="file" accept="audio/*,video/*" onChange={(event: ChangeEvent<HTMLInputElement>) => choose(event.target.files?.[0])}/>
        <div className="icon">{busy ? "◌" : "↑"}</div>
        <h2>{file ? file.name : "Drop your song here"}</h2>
        <p>{file ? `${(file.size / 1024 / 1024).toFixed(1)} MB · ready to forge` : "Audio or video. We’ll handle the rest."}</p>
        {!busy && <button className="primary" onClick={(event) => { event.stopPropagation(); inputRef.current?.click(); }}>{file ? "Choose another file" : "Choose a file"}</button>}
        {!busy && file && <button className="secondary" onClick={(event) => { event.stopPropagation(); start(); }}>Create karaoke video</button>}
        <div className="formats">MP3 · WAV · M4A · FLAC · MP4 · MOV · MKV · WEBM</div>
      </div>
      {(busy || job) && <div className="statusPanel"><div className="statusTop"><div><b>{job.message || "Processing"}</b><span>{job.filename}</span></div><strong>{percent}%</strong></div><div className="bar"><div style={{ width: `${percent}%` }}/></div><div className="steps">{stages.map((stage, index) => <div key={stage} className={index < stageIndex || (index === stageIndex && percent >= [15, 40, 65, 88][index]) ? "step active" : "step"}><span>{index < stageIndex ? "✓" : index + 1}</span>{stage}</div>)}</div></div>}
      {error && <div className="error">{error}</div>}
      {job?.status === "failed" && <button className="secondary wide" onClick={() => { setJob(null); setError(""); }}>Try again</button>}
    </section> : <section className="result">
      <div className="resultHeader"><div><div className="eyebrow">✓ Karaoke ready</div><h2>{job.filename || "Your karaoke video"}</h2><p>{job.wordCount ?? 0} timed words · {job.segmentCount ?? 0} lyric segments</p></div><button className="secondary" onClick={reset}>Create another</button></div>
      <div className="player"><video controls playsInline src={previewUrl}/></div>
      <div className="actions"><a className="primary action" href={downloadUrl}>Download MP4</a><a className="secondary action" href={previewUrl} target="_blank" rel="noreferrer">Open preview</a></div>
    </section>}

    <section className="features"><div className="feature"><b>🎚 Clean instrumental</b><span>Demucs separates vocals from the accompaniment with no paid AI API.</span></div><div className="feature"><b>📝 Word-synced lyrics</b><span>Whisper timestamps individual words so the karaoke highlight follows the singer.</span></div><div className="feature"><b>🎬 YouTube-ready render</b><span>1080p H.264 video with AAC audio and burned-in karaoke subtitles.</span></div></section>
    <div className="footer">Only upload media you own or have permission to process and publish.</div>
  </main>;
}
