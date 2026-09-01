import { NextResponse } from "next/server";

export async function GET(_: Request, { params }: { params: Promise<{ jobId: string }> }) {
  const workerUrl = process.env.KARAOKEFORGE_WORKER_URL;
  if (!workerUrl) return NextResponse.json({ error: "Worker is not connected yet." }, { status: 503 });
  const { jobId } = await params;
  const response = await fetch(`${workerUrl.replace(/\/$/, "")}/jobs/${jobId}/lyrics`, { cache: "no-store" });
  return NextResponse.json(await response.json(), { status: response.status });
}
