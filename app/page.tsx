'use client';

import { ChangeEvent, useState } from 'react';

export default function Home() {
  const [fileName, setFileName] = useState('');
  const [message, setMessage] = useState('');

  function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setMessage('File selected. Processing engine will be connected next.');
  }

  return (
    <main className="shell">
      <nav className="nav">
        <div className="brand">Karaoke<span>Forge</span></div>
        <div className="badge">Open-source processing</div>
      </nav>

      <section className="hero">
        <div className="eyebrow">🎤 AI karaoke studio</div>
        <h1>Forge a song into <em>karaoke.</em></h1>
        <p>Upload a song and turn it into a clean instrumental with synchronized sing-along lyrics and a YouTube-ready video.</p>
      </section>

      <section className="card">
        <div className="drop">
          <div className="icon">↑</div>
          <h2>{fileName || 'Drop your song here'}</h2>
          <p>{message || 'Audio or video. We’ll handle the rest.'}</p>
          <label className="upload">Choose a file<input className="hidden" type="file" accept="audio/*,video/*" onChange={handleFile} /></label>
          <div className="formats">MP3 · WAV · M4A · MP4 · MOV</div>
        </div>
      </section>

      <section className="features">
        <div className="feature"><b>🎚 Vocal separation</b><span>Open-source source separation keeps the instrumental clean.</span></div>
        <div className="feature"><b>📝 Synced lyrics</b><span>Automatic transcription with timing for sing-along playback.</span></div>
        <div className="feature"><b>🎬 YouTube ready</b><span>Render a polished karaoke video in a standard MP4 format.</span></div>
      </section>

      <div className="footer">Only upload music you have permission to process and publish.</div>
    </main>
  );
}