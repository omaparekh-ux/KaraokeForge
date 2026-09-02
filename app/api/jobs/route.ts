import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const allowed = new Set(["mp3", "wav", "m4a", "aac", "flac", "ogg", "mp4", "mov", "mkv", "webm"]);

export async function POST(request: Request) {
  const workerUrl = process.env.KARAOKEFORGE_WORKER_URL;
  if (!workerUrl) {
    return NextResponse.json({ error: "Karaoke worker is not configured yet." }, { status: 503 });
  }

  const form = await request.formData();
  const file = form.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "No media file supplied." }, { status: 400 });
  }

  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!allowed.has(extension)) {
    return NextResponse.json({ error: `Unsupported file type: .${extension || "unknown"}` }, { status: 415 });
  }

  const upstream = new FormData();
  upstream.append("file", file, file.name);
  try {
    const response = await fetch(`${workerUrl.replace(/\/$/, "")}/jobs`, {
      method: "POST",
      body: upstream,
      cache: "no-store",
    });
    const data = await response.json();
    return NextResponse.json(data, {
      status: response.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json({ error: "Could not reach the karaoke worker." }, { status: 502 });
  }
}
