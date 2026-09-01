"use client";

import { ChangeEvent, useEffect, useRef, useState } from "react";

type Status = "idle" | "uploading" | "extracting" | "separating" | "transcribing" | "rendering" | "complete" | "failed";

const steps = ["Upload", "Separate vocals", "Transcribe lyrics", "Render video"];
const stepMap: Record<Exclude<Status, "idle" | "uploading" | "failed" | "complete">, number> = { extracting: 1, separating: 2, transcribing: 3, rendering: 4 };

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [jobId, setJobId] = useState("");
  const [error, setError] = useState("");

  function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0];
    if (!selected) return;
    setFile(selected); setStatus("idle"); setError(""); setJobId("");
  }

  useEffect(() => {
    if (!jobId || status === "complete" || status === "failed") return;
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}`, { cache: "no-store" });
        const data = await res.json();
        if (res.ok) {
          setStatus(data.status as Status);
          if (data.status === "failed") setError(data.error || "Processing failed.");
        }
      } catch { /* transient polling failure */ }
    }, 2500);
    return () => clearInterval(timer);
  }, [jobId, status]);

  async function start() {
    if (!file) return;
    setStatus("uploading"); setError("");
    const form = new FormData(); form.append("file", file);
    try {
      const res = await fetch("/api/jobs", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Could not start processing.");
      setJobId(data.jobId); setStatus("extracting");
    } catch (e) { setStatus("failed"); setError(e instanceof Error ? e.message : "Upload failed."); }
  }

  const active = status === "uploading" ? 1 : status === "extracting" ? 1 : status === "separating" ? 2 : status === "transcribing" ? 3 : status === "rendering" ? 4 : status === "complete" ? 4 : 0;
  const downloadUrl = jobId ? `/api/jobs/${jobId}/download` : "";

  return <main className="shell">
    <nav className="nav"><div className="brand">Karaoke<span>Forge</span></div><div className="badge">Open-source processing</div></nav>
    <section className="hero"><div className="eyebrow">🎤 AI karaoke studio</div><h1>Forge a song into <em>karaoke.</em></h1><p>Upload a song and turn it into a clean instrumental with synchronized sing-along lyrics and a YouTube-ready video.</p></section>
    <section className="card">
      <div className="drop">
        <div className="icon">{status === "complete" ? "✓" : "↑"}</div>
        <h2>{file ? file.name : "Drop your song here"}</h2>
        <p>{file ? `${(file.size / 1024 / 1024).toFixed(1)} MB · ready to process` : "Audio or video. We’ll handle the rest."}</p>
        <label className="upload">{file ? "Choose another file" : "Choose a file"}<input ref={inputRef} className="hidden" type="file" accept="audio/*,video/*" onChange={handleFile}/></label>
        <button className="upload" style={{marginTop:10}} disabled={!file || ["uploading","extracting","separating","transcribing","rendering"].includes(status)} onClick={start}>{status === "complete" ? "Create another" : status === "idle" || status === "failed" ? "Create karaoke video" : "Processing…"}</button>
        <div className="formats">MP3 · WAV · M4A · MP4 · MOV</div>
      </div>
      {active > 0 && <div className="progress">{steps.map((step, i) => <div className={i + 1 <= active ? "progressStep active" : "progressStep"} key={step}><span>{i + 1 <= active ? "✓" : i + 1}</span>{step}</div>)}</div>}
      {error && <div className="error">{error}</div>}
      {status === "complete" && <a className="download" href={downloadUrl}>Download karaoke MP4</a>}
    </section>
    <section className="features"><div className="feature"><b>🎚 Vocal separation</b><span>Demucs separates the singer from the accompaniment without a paid API.</span></div><div className="feature"><b>📝 Synced lyrics</b><span>Whisper creates timestamped lyrics for sing-along timing.</span></div><div className="feature"><b>🎬 YouTube ready</b><span>FFmpeg renders the instrumental and karaoke subtitles into MP4.</span></div></section>
    <div className="footer">Only upload music you have permission to process and publish.</div>
  </main>;
}
