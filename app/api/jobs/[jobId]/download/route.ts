export async function GET(_: Request, { params }: { params: Promise<{ jobId: string }> }) {
  const workerUrl = process.env.KARAOKEFORGE_WORKER_URL;
  if (!workerUrl) return new Response("Worker is not connected yet.", { status: 503 });
  const { jobId } = await params;
  const response = await fetch(`${workerUrl.replace(/\/$/, "")}/jobs/${jobId}/download`, { cache: "no-store" });
  if (!response.ok) return new Response(await response.text(), { status: response.status });
  return new Response(response.body, { status: 200, headers: { "Content-Type": "video/mp4", "Content-Disposition": "attachment; filename=karaokeforge.mp4" } });
}
