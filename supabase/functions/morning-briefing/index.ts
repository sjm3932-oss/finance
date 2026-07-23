// Morning briefing: snapshot context → Gemini → Web Push to all subscriptions
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import webpush from "npm:web-push@3.6.7";

async function geminiBrief(prompt: string, apiKey: string) {
  const model = Deno.env.get("GEMINI_MODEL") ?? "gemini-2.5-flash";
  const url =
    `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: { temperature: 0.4 },
    }),
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`Gemini ${res.status}: ${t}`);
  }
  const data = await res.json();
  const text = data?.candidates?.[0]?.content?.parts?.map((p: { text?: string }) => p.text ?? "")
    .join("") ?? "";
  if (!text) throw new Error("Empty Gemini briefing");
  return text.trim();
}

Deno.serve(async (_req) => {
  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );
    const geminiKey = Deno.env.get("GEMINI_API_KEY");
    if (!geminiKey) throw new Error("GEMINI_API_KEY missing in function secrets");

    // Ensure today's snapshot exists
    await supabase.rpc("compute_daily_snapshot");

    const { data: snap } = await supabase
      .from("daily_snapshots")
      .select("*")
      .order("snapshot_date", { ascending: false })
      .limit(1)
      .maybeSingle();

    const { data: portfolio } = await supabase.from("v_portfolio").select("*");
    const { data: fx } = await supabase
      .from("market_prices")
      .select("price,updated_at")
      .eq("ticker", "USDKRW")
      .maybeSingle();

    const prompt = `당신은 부부 공동자산 비서입니다. 아래 JSON을 바탕으로 한국어로 아침 브리핑을 작성하세요.
3~6문장, 핵심만. 순자산/투자자산/부채, 두드러진 종목 등락, 오늘 체크할 액션 1개를 포함하세요.
데이터:
snapshot=${JSON.stringify(snap)}
usdkrw=${JSON.stringify(fx)}
portfolio=${JSON.stringify((portfolio ?? []).slice(0, 30))}`;

    const briefing = await geminiBrief(prompt, geminiKey);

    await supabase.from("ai_chat_logs").insert({
      user_query: "morning_briefing",
      ai_response: briefing,
      context_summary: JSON.stringify({ snap, fx }),
    });

    const vapidPublic = Deno.env.get("VAPID_PUBLIC_KEY");
    const vapidPrivate = Deno.env.get("VAPID_PRIVATE_KEY");
    const vapidSubject = Deno.env.get("VAPID_SUBJECT") ?? "mailto:sjm3932@gmail.com";

    let pushSent = 0;
    let pushErrors: string[] = [];
    if (vapidPublic && vapidPrivate) {
      webpush.setVapidDetails(vapidSubject, vapidPublic, vapidPrivate);
      const { data: subs } = await supabase.from("push_subscriptions").select("*");
      const payload = JSON.stringify({
        title: "부자뚱",
        body: briefing.slice(0, 180),
        url: Deno.env.get("PUBLIC_APP_URL") ?? "/",
      });
      for (const sub of subs ?? []) {
        try {
          await webpush.sendNotification(
            {
              endpoint: sub.endpoint,
              keys: { p256dh: sub.p256dh_key, auth: sub.auth_key },
            },
            payload,
          );
          pushSent++;
        } catch (e) {
          pushErrors.push(String(e));
          // Drop gone subscriptions
          if (String(e).includes("410") || String(e).includes("404")) {
            await supabase.from("push_subscriptions").delete().eq("id", sub.id);
          }
        }
      }
    }

    return Response.json({
      ok: true,
      briefing,
      pushSent,
      pushErrors: pushErrors.slice(0, 5),
    });
  } catch (e) {
    return Response.json({ ok: false, error: String(e) }, { status: 500 });
  }
});
