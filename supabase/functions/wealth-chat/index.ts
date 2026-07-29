// Wealth chat: JWT user → rebuild context → Gemini → ai_chat_logs
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import {
  corsHeaders,
  json,
  requireUser,
  serviceClient,
} from "../_shared/gemini.ts";

const WEALTH_CHAT_SYSTEM = `당신은 부자뚱의 종합 자산관리 전문가입니다.
정명·지수 공동자산(주식·현금·부채·세금·순자산)을 함께 살펴 보는 든든한 파트너처럼 대화하세요.

말투:
- 존댓말로 따뜻하고 친절하게. 딱딱한 보고서 톤은 피하세요.
- 핵심을 먼저 말하고, 필요하면 짧은 설명·다음 확인 포인트를 덧붙이세요.
- 걱정되는 숫자도 과장하지 말고, 차분히 짚어 주세요.
- 이모지는 쓰지 마세요.

규칙:
1. 제공된 WEALTH_CONTEXT JSON의 포트폴리오/시세/스냅샷/세금/macro_indicators 수치를 사실의 1순위 근거로 쓰세요.
2. 코스피·S&P500·나스닥·원달러환율·국제유가(WTI)·미국 금리(단기·10년) 질문은 macro_indicators를 우선 인용하세요. 값이 있으면 "데이터에 없다"고 하지 마세요.
3. 과거 로그의 숫자와 현재 holdings/prices/macro가 다르면 현재 수치를 우선하고, 달라졌다면 짧게 알려 주세요.
4. 컨텍스트에 없는 개별 종목·뉴스는 추측하지 말고 "지금 데이터에 없어요"라고 말하세요.
5. 특정 종목 매수·매도 권유나 세금 확정 자문은 하지 마세요. 필요하면 참고용 추정임을 밝히세요.
6. 한국어로 답하고, 숫자에는 단위(원/달러/%/포인트)를 붙이세요.
7. 자산·시세·가계 재무와 무관한 주제는 정중히 범위 밖이라고 안내하세요.`;

const UA = { "User-Agent": "Bujattung/1.0" };

type MacroRow = {
  key: string;
  label: string;
  value: number | null;
  unit: string;
  source: string;
  updated_at: string | null;
  error?: string;
};

async function yahooLast(symbol: string): Promise<number> {
  const url =
    `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1d&range=5d`;
  const res = await fetch(url, { headers: UA });
  if (!res.ok) throw new Error(`Yahoo ${symbol} HTTP ${res.status}`);
  const payload = await res.json();
  const result = payload?.chart?.result?.[0];
  if (!result) throw new Error(`Yahoo ${symbol} empty`);
  const meta = result.meta ?? {};
  let price = meta.regularMarketPrice;
  if (price == null) {
    const closes = result.indicators?.quote?.[0]?.close ?? [];
    for (let i = closes.length - 1; i >= 0; i--) {
      if (closes[i] != null) {
        price = closes[i];
        break;
      }
    }
  }
  if (price == null) throw new Error(`Yahoo ${symbol} no price`);
  return Number(price);
}

async function frankfurterUsdKrw(): Promise<number> {
  const res = await fetch(
    "https://api.frankfurter.dev/v1/latest?from=USD&to=KRW"
  );
  if (!res.ok) throw new Error(`FX HTTP ${res.status}`);
  const data = await res.json();
  const rate = data?.rates?.KRW;
  if (rate == null) throw new Error("FX missing KRW");
  return Number(rate);
}

/** Live macro indicators used to answer market questions in chat. */
async function fetchMacroIndicators(): Promise<MacroRow[]> {
  const now = new Date().toISOString();
  const specs: {
    key: string;
    label: string;
    unit: string;
    source: string;
    run: () => Promise<number>;
  }[] = [
    {
      key: "KOSPI",
      label: "코스피",
      unit: "pt",
      source: "Yahoo ^KS11",
      run: () => yahooLast("^KS11"),
    },
    {
      key: "SP500",
      label: "S&P 500",
      unit: "pt",
      source: "Yahoo ^GSPC",
      run: () => yahooLast("^GSPC"),
    },
    {
      key: "NASDAQ",
      label: "나스닥",
      unit: "pt",
      source: "Yahoo ^IXIC",
      run: () => yahooLast("^IXIC"),
    },
    {
      key: "USDKRW",
      label: "원달러환율",
      unit: "KRW",
      source: "Frankfurter",
      run: () => frankfurterUsdKrw(),
    },
    {
      key: "WTI",
      label: "WTI 국제유가",
      unit: "USD/bbl",
      source: "Yahoo CL=F",
      run: () => yahooLast("CL=F"),
    },
    {
      key: "US_IRX",
      label: "미국 단기금리(13주 T-Bill)",
      unit: "%",
      source: "Yahoo ^IRX",
      run: () => yahooLast("^IRX"),
    },
    {
      key: "US10Y",
      label: "미국 10년물 금리",
      unit: "%",
      source: "Yahoo ^TNX",
      run: () => yahooLast("^TNX"),
    },
  ];

  const settled = await Promise.all(
    specs.map(async (s) => {
      try {
        const value = await s.run();
        return {
          key: s.key,
          label: s.label,
          value,
          unit: s.unit,
          source: s.source,
          updated_at: now,
        } satisfies MacroRow;
      } catch (e) {
        return {
          key: s.key,
          label: s.label,
          value: null,
          unit: s.unit,
          source: s.source,
          updated_at: null,
          error: e instanceof Error ? e.message : String(e),
        } satisfies MacroRow;
      }
    })
  );
  return settled;
}

async function persistMacros(
  admin: ReturnType<typeof serviceClient>,
  macros: MacroRow[]
) {
  const now = new Date().toISOString();
  const rows = macros
    .filter((m) => m.value != null && Number.isFinite(m.value))
    .map((m) => ({
      ticker: m.key,
      price: m.value as number,
      currency: m.unit.includes("KRW") ? "KRW" : m.unit.includes("%") ? "PCT" : "USD",
      updated_at: now,
    }));
  if (rows.length) {
    await admin.from("market_prices").upsert(rows);
  }

  const byKey = Object.fromEntries(
    macros.filter((m) => m.value != null).map((m) => [m.key, m.value])
  );
  const today = now.slice(0, 10);
  await admin.from("market_index_snapshots").upsert({
    snapshot_date: today,
    usdkrw: byKey.USDKRW ?? null,
    kospi: byKey.KOSPI ?? null,
    sp500: byKey.SP500 ?? null,
    nasdaq: byKey.NASDAQ ?? null,
  });
}

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
    indexSnaps,
    macros,
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
    admin
      .from("market_index_snapshots")
      .select("snapshot_date,kospi,sp500,nasdaq,usdkrw")
      .order("snapshot_date", { ascending: false })
      .limit(7),
    fetchMacroIndicators(),
  ]);

  // Best-effort persist for next cron / UI
  try {
    await persistMacros(admin, macros);
  } catch {
    /* ignore persist errors — chat can still answer from live macros */
  }

  const priceMap = new Map(
    (prices.data || []).map((p: { ticker: string }) => [p.ticker, p])
  );
  const usdkrwLive = macros.find((m) => m.key === "USDKRW")?.value;
  const usdkrw =
    usdkrwLive ??
    (priceMap.get("USDKRW") as { price?: number } | undefined)?.price;

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
    macro_indicators: macros,
    recent_index_snapshots: indexSnaps.data || [],
    note:
      "macro_indicators는 대화 시점에 실시간 조회한 주요 시장 지표입니다. 한국/미국 기준금리는 공개 API 제한으로 미국 T-Bill·10년물로 대체 관측합니다.",
    recent_chat_logs: (chatLogs.data || []).reverse(),
    meta: {
      holdings: enriched.length,
      usdkrw,
      macros_ok: macros.filter((m) => m.value != null).length,
    },
  };

  let text = JSON.stringify(ctx);
  if (text.length > 16000) text = text.slice(0, 16000) + "…(truncated)";
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
