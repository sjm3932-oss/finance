// Stable public gateway.
// - Always bookmarked as this fixed URL
// - Health-checks live Streamlit origins before redirecting
// - Shows a Korean retry page instead of sending users to a dead tunnel
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";

const cors: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Cache-Control": "no-store",
};

function htmlRetry(message: string): Response {
  const body = `<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta http-equiv="refresh" content="5"/>
<title>연결 준비 중</title>
<style>
body{margin:0;min-height:100vh;display:grid;place-items:center;font-family:Pretendard,Apple SD Gothic Neo,sans-serif;background:#F4F6F5;color:#1A1A1A}
.card{width:min(420px,92vw);padding:28px 22px;border-radius:20px;background:#fff;border:1px solid #E5E7EB;box-shadow:0 12px 40px rgba(3,199,90,.12)}
.brand{color:#03C75A;font-weight:800;margin-bottom:8px}
h1{font-size:1.25rem;margin:0 0 10px}
p{color:#6B7280;line-height:1.5;margin:0}
</style></head>
<body><div class="card">
<div class="brand">Couples Wealth Master</div>
<h1>앱 서버에 다시 연결하는 중…</h1>
<p>${message}</p>
<p style="margin-top:12px">이 페이지는 5초마다 자동으로 다시 시도합니다. 북마크는 이 주소만 사용하세요.</p>
</div></body></html>`;
  return new Response(body, {
    status: 503,
    headers: { ...cors, "Content-Type": "text/html; charset=utf-8" },
  });
}

async function isHealthy(origin: string): Promise<boolean> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 8000);
    const res = await fetch(`${origin.replace(/\/$/, "")}/_stcore/health`, {
      signal: ctrl.signal,
      redirect: "follow",
    });
    clearTimeout(t);
    return res.ok;
  } catch {
    return false;
  }
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
    const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
    const anonKey = Deno.env.get("SUPABASE_ANON_KEY") ?? "";
    const key = serviceKey || anonKey;
    if (!supabaseUrl || !key) {
      return htmlRetry("서버 설정이 아직 준비되지 않았습니다.");
    }

    const sb = createClient(supabaseUrl, key);
    const { data, error } = await sb
      .from("app_runtime")
      .select("public_url, fallback_url")
      .eq("id", 1)
      .maybeSingle();

    if (error || !data?.public_url) {
      return htmlRetry("앱 주소가 아직 등록되지 않았습니다. 잠시만 기다려 주세요.");
    }

    const candidates = [data.public_url, data.fallback_url]
      .filter((u): u is string => !!u)
      .map((u) => u.replace(/\/$/, ""));

    let chosen: string | null = null;
    for (const origin of candidates) {
      if (await isHealthy(origin)) {
        chosen = origin;
        break;
      }
    }

    if (!chosen) {
      return htmlRetry(
        "일시적으로 터널이 끊겼습니다. 자동 복구 중이니 이 페이지를 유지해 주세요.",
      );
    }

    const incoming = new URL(req.url);
    const dest = new URL(chosen);
    for (const [k, v] of incoming.searchParams.entries()) {
      dest.searchParams.set(k, v);
    }

    return new Response(null, {
      status: 302,
      headers: { ...cors, Location: dest.toString() },
    });
  } catch (err) {
    return htmlRetry(`게이트웨이 오류: ${String(err)}`);
  }
});
