// Wealth chat: JWT user → rebuild context → Gemini → ai_chat_logs
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import {
  corsHeaders,
  json,
  requireUser,
  serviceClient,
} from "../_shared/gemini.ts";

const WEALTH_CHAT_SYSTEM = `당신은 부자뚱의 종합 자산관리 전문가입니다.
부부 공동자산(주식·현금·부채·세금·순자산)을 함께 살펴 보는 든든한 파트너처럼 대화하세요.

말투:
- 존댓말로 따뜻하고 친절하게. 딱딱한 보고서 톤은 피하세요.
- 핵심을 먼저 말하고, 필요하면 짧은 설명·다음 확인 포인트를 덧붙이세요.
- 걱정되는 숫자도 과장하지 말고, 차분히 짚어 주세요.
- 이모지는 쓰지 마세요.

규칙:
1. 제공된 WEALTH_CONTEXT JSON의 포트폴리오/시세/스냅샷/세금 수치를 사실의 1순위 근거로 쓰세요.
2. 과거 로그의 숫자와 현재 holdings/prices가 다르면 현재 수치를 우선하고, 달라졌다면 짧게 알려 주세요.
3. 컨텍스트에 없는 시세·뉴스·종목은 추측하지 말고 "지금 데이터에 없어요"라고 말하세요.
4. 특정 종목 매수·매도 권유나 세금 확정 자문은 하지 마세요. 필요하면 참고용 추정임을 밝히세요.
5. 한국어로 답하고, 숫자에는 단위(원/달러/%)를 붙이세요.
6. 자산·가계 재무와 무관한 주제는 정중히 범위 밖이라고 안내하세요.`;

async function buildContext(admin: ReturnType<typeof serviceClient>) {
  const [
    holdings,
    prices,
    accounts,
    debts,
    trades,
    snaps,
    taxView,
    portfolio,
    dividends,
    chatLogs,
  ] = await Promise.all([
    admin.from("holdings").select("*"),
    admin.from("market_prices").select("*"),
    admin.from("accounts").select("id,institution,account_type,currency"),
    admin.from("debts").select("*"),
    admin
      .from("trades")
      .select("trade_date,ticker,trade_type,price,quantity,reason,account_id")
      .order("trade_date", { ascending: false })
      .limit(30),
    admin
      .from("daily_snapshots")
      .select("*")
      .order("snapshot_date", { ascending: false })
      .limit(14),
    admin.from("v_tax_calculation").select("*"),
    admin.from("v_portfolio").select("*"),
    admin
      .from("dividends")
      .select("pay_date,ticker,amount,currency,memo")
      .order("pay_date", { ascending: false })
      .limit(30),
    admin
      .from("ai_chat_logs")
      .select("user_query,ai_response,created_at")
      .neq("user_query", "morning_briefing")
      .order("created_at", { ascending: false })
      .limit(16),
  ]);

  const priceMap = new Map(
    (prices.data || []).map((p: { ticker: string }) => [p.ticker, p])
  );
  const usdkrw = (priceMap.get("USDKRW") as { price?: number } | undefined)?.price;

  const enriched = (holdings.data || []).map((h: Record<string, unknown>) => {
    const mp = priceMap.get(String(h.ticker)) as
      | { price?: number; currency?: string }
      | undefined;
    const qty = Number(h.quantity || 0);
    const avg = Number(h.avg_price || 0);
    const px = mp?.price != null ? Number(mp.price) : null;
    const ccy = String(h.currency || mp?.currency || "KRW");
    const mv = px != null ? px * qty : null;
    return {
      ticker: h.ticker,
      name: h.name,
      quantity: qty,
      avg_price: avg,
      currency: ccy,
      current_price: px,
      market_value: mv,
      return_pct: px != null && avg ? ((px - avg) / avg) * 100 : null,
    };
  });

  const ctx = {
    holdings: enriched,
    accounts: accounts.data || [],
    debts: debts.data || [],
    recent_trades: trades.data || [],
    recent_snapshots: snaps.data || [],
    tax: taxView.data || [],
    portfolio: (portfolio.data || []).slice(0, 40),
    dividends: dividends.data || [],
    usdkrw,
    recent_chat_logs: (chatLogs.data || []).reverse(),
    meta: { holdings: enriched.length, usdkrw },
  };

  let text = JSON.stringify(ctx);
  if (text.length > 14000) text = text.slice(0, 14000) + "…(truncated)";
  return { ctx, text };
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  try {
    if (req.method !== "POST") return json({ ok: false, error: "POST only" }, 405);

    const { supabase, user } = await requireUser(req);
    const body = await req.json();
    const message = String(body.message || "").trim();
    if (!message) return json({ ok: false, error: "message required" }, 400);

    const history = Array.isArray(body.history) ? body.history.slice(-40) : [];
    const admin = serviceClient();
    const { ctx, text: contextText } = await buildContext(admin);

    // Build multimodal-style text conversation for Gemini REST
    const turns: { role: string; parts: { text: string }[] }[] = [];
    turns.push({
      role: "user",
      parts: [
        {
          text:
            `WEALTH_CONTEXT:\n${contextText}\n\n` +
            `위 컨텍스트를 기준으로 답하세요. 준비되면 "준비됨"이라고만 답하세요.`,
        },
      ],
    });
    turns.push({ role: "model", parts: [{ text: "준비됨" }] });

    for (const h of history) {
      const role = h.role === "model" || h.role === "assistant" ? "model" : "user";
      const content = String(h.content || "").trim();
      if (!content) continue;
      turns.push({ role, parts: [{ text: content }] });
    }
    turns.push({ role: "user", parts: [{ text: message }] });

    const apiKey = Deno.env.get("GEMINI_API_KEY");
    if (!apiKey) throw new Error("GEMINI_API_KEY missing");
    const model = Deno.env.get("GEMINI_MODEL") ?? "gemini-2.5-flash";
    const url =
      `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;

    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: WEALTH_CHAT_SYSTEM }] },
        contents: turns,
        generationConfig: { temperature: 0.3 },
      }),
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(`Gemini ${res.status}: ${t.slice(0, 400)}`);
    }
    const data = await res.json();
    const reply =
      data?.candidates?.[0]?.content?.parts
        ?.map((p: { text?: string }) => p.text ?? "")
        .join("")
        ?.trim() || "";
    if (!reply) throw new Error("Empty Gemini reply");

    await supabase.from("ai_chat_logs").insert({
      user_id: user.id,
      user_query: message,
      ai_response: reply,
      context_summary: contextText.slice(0, 2000),
    });

    return json({
      ok: true,
      reply,
      meta: ctx.meta,
    });
  } catch (e) {
    if (e instanceof Response) return e;
    return json(
      { ok: false, error: e instanceof Error ? e.message : "unknown" },
      500
    );
  }
});
