// KIS (한투) sync enqueue only. Open API calls run on the same static-IP
// cloud worker as Toss (scripts/toss_sync_worker.py also claims kis jobs).
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import {
  corsHeaders,
  json,
  requireCoupleUser,
  serviceClient,
} from "../_shared/gemini.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  try {
    const admin = serviceClient();

    async function workerStatus() {
      const { data: worker } = await admin
        .from("toss_sync_worker")
        .select("public_ip,seen_at")
        .eq("id", 1)
        .maybeSingle();
      const seen = worker?.seen_at ? Date.parse(String(worker.seen_at)) : 0;
      const stale = !seen || Date.now() - seen > 2 * 60 * 1000;
      return {
        worker_ip: worker?.public_ip ?? null,
        worker_seen_at: worker?.seen_at ?? null,
        worker_online: !stale && !!worker?.public_ip,
      };
    }

    if (req.method === "GET") {
      const w = await workerStatus();
      return json({ ok: true, mode: "cloud-worker", ...w });
    }

    if (req.method !== "POST") return json({ ok: false, error: "POST only" }, 405);
    const { user } = await requireCoupleUser(req);

    let body: Record<string, unknown> = {};
    try {
      body = (await req.json()) as Record<string, unknown>;
    } catch {
      body = {};
    }

    if (body.probe) {
      const w = await workerStatus();
      return json({ ok: true, mode: "cloud-worker", ...w });
    }

    if (typeof body.job_id === "string" && body.job_id) {
      const { data: job, error } = await admin
        .from("kis_sync_jobs")
        .select("id,status,error,result,created_at,finished_at")
        .eq("id", body.job_id)
        .maybeSingle();
      if (error || !job) return json({ ok: false, error: "작업을 찾을 수 없습니다." }, 404);
      return json({ ok: true, job });
    }

    const { data: job, error } = await admin
      .from("kis_sync_jobs")
      .insert({ user_id: user.id, status: "queued" })
      .select("id,status,created_at")
      .single();
    if (error || !job) {
      return json({
        ok: false,
        error: error?.message || "작업을 넣지 못했습니다. 마이그레이션 0027 을 적용했는지 확인하세요.",
      }, 400);
    }

    const w = await workerStatus();
    return json({
      ok: true,
      queued: true,
      job_id: job.id,
      worker_online: w.worker_online,
      worker_ip: w.worker_ip,
    });
  } catch (e) {
    if (e instanceof Response) return e;
    return json({ ok: false, error: e instanceof Error ? e.message : "kis-sync failed" }, 500);
  }
});
