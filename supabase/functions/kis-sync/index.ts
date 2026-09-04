// KIS (한투) sync: save app keys in DB and run Open API from this function.
// SSH / Cloud Shell / worker env is not required for "지금 동기화".
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import {
  corsHeaders,
  json,
  requireCoupleUser,
  serviceClient,
} from "../_shared/gemini.ts";
import {
  DEFAULT_ACCOUNTS,
  loadKisSettings,
  parseAccounts,
  runKisSync,
  settingsPublic,
} from "../_shared/kis.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  try {
    const admin = serviceClient();

    async function settingsStatus() {
      const { data } = await admin
        .from("kis_api_settings")
        .select("app_key,app_secret,accounts,env")
        .eq("id", 1)
        .maybeSingle();
      return settingsPublic(data || {});
    }

    if (req.method === "GET") {
      return json({
        ok: true,
        mode: "edge",
        default_accounts: DEFAULT_ACCOUNTS,
        ...(await settingsStatus()),
      });
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
      return json({
        ok: true,
        mode: "edge",
        worker_online: true,
        default_accounts: DEFAULT_ACCOUNTS,
        ...(await settingsStatus()),
      });
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

    if (body.save) {
      const appKeyIn = String(body.app_key || "").trim();
      const appSecretIn = String(body.app_secret || "").trim();
      const accountsIn = String(body.accounts || "").trim();
      const envIn = String(body.env || "real").trim() === "demo" ? "demo" : "real";

      const { data: existing } = await admin
        .from("kis_api_settings")
        .select("app_key,app_secret,accounts,env")
        .eq("id", 1)
        .maybeSingle();

      const nextKey = appKeyIn || String(existing?.app_key || "").trim();
      const nextSecret = appSecretIn || String(existing?.app_secret || "").trim();
      const accounts = accountsIn || String(existing?.accounts || "").trim() || DEFAULT_ACCOUNTS;
      const parsed = parseAccounts("", "01", accounts);
      if (!nextKey || !nextSecret) {
        return json({ ok: false, error: "앱키와 앱시크릿을 모두 입력하세요." }, 400);
      }
      if (!parsed.length) {
        return json({
          ok: false,
          error: "계좌를 12345678-01 형식으로 입력하세요. 여러 좌는 쉼표로 구분합니다.",
        }, 400);
      }
      const keyChanged = nextKey !== String(existing?.app_key || "") ||
        nextSecret !== String(existing?.app_secret || "");
      const { error } = await admin.from("kis_api_settings").upsert({
        id: 1,
        app_key: nextKey,
        app_secret: nextSecret,
        accounts,
        env: envIn,
        updated_at: new Date().toISOString(),
        updated_by: user.id,
        ...(keyChanged ? { access_token: null, token_expires_at: null } : {}),
      });
      if (error) {
        return json({
          ok: false,
          error: error.message.includes("kis_api_settings")
            ? "설정 테이블이 없습니다. 마이그레이션 0028 을 적용하세요."
            : error.message,
        }, 400);
      }
      return json({
        ok: true,
        saved: true,
        ...settingsPublic({ app_key: nextKey, app_secret: nextSecret, accounts, env: envIn }),
      });
    }

    const ready = await loadKisSettings(admin);
    if (!ready) {
      return json({
        ok: false,
        error: "먼저 앱키·앱시크릿·계좌를 저장하세요. Cloud Shell이나 SSH는 필요 없습니다.",
      }, 400);
    }

    const now = new Date().toISOString();
    const { data: job, error } = await admin
      .from("kis_sync_jobs")
      .insert({ user_id: user.id, status: "running", started_at: now })
      .select("id,status,created_at")
      .single();
    if (error || !job) {
      return json({
        ok: false,
        error: error?.message || "작업을 넣지 못했습니다. 마이그레이션 0027 을 적용했는지 확인하세요.",
      }, 400);
    }

    try {
      const result = await runKisSync(admin, { userId: user.id, lookbackDays: 365 });
      await admin
        .from("kis_sync_jobs")
        .update({ status: "ok", result, finished_at: new Date().toISOString(), error: null })
        .eq("id", job.id);
      return json({
        ok: true,
        ran: true,
        job_id: job.id,
        worker_online: true,
        ...result,
      });
    } catch (e) {
      const message = e instanceof Error ? e.message : "kis-sync failed";
      await admin
        .from("kis_sync_jobs")
        .update({ status: "error", error: message.slice(0, 800), finished_at: new Date().toISOString() })
        .eq("id", job.id);
      return json({ ok: false, error: message, job_id: job.id }, 400);
    }
  } catch (e) {
    if (e instanceof Response) return e;
    return json({ ok: false, error: e instanceof Error ? e.message : "kis-sync failed" }, 500);
  }
});
