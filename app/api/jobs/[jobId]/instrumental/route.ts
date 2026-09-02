import { NextResponse } from "next/server";

export async function GET(_: Request, { params }: { params: Promise<{ jobId: string }> }) {
  const workerUrl = process.env.KARAOKEFORGE_WORKER_URL;
  if (!workerUrl) return new NextResponse("Worker is not connected yet.", { status: 503 });
  const { jobId } = await params;
  const response = await fetch(`${workerUrl.replace(/\/$/, "")}/jobs/${jobId}/instrumental`, { cache: "no-store" });
  if (!response.ok) return new NextResponse(await response.text(), { status: response.status });
  return new Response(response.body, { status: 200, headers: { "Content-Type": "audio/wav", "Content-Disposition": "attachment", "Cache-Control": "private, no-store" } });
}
