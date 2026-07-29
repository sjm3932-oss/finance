// Wealth chat: portfolio DB + live macros/moves/news + Gemini Google Search grounding
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import {
  corsHeaders,
  json,
  requireUser,
  serviceClient,
} from "../_shared/gemini.ts";

const WEALTH_CHAT_SYSTEM = `당신은 부자뚱의 종합 자산관리 전문가입니다.
정명·지수의 공동자산과 외부 시장을 연결해, 객관적으로 설명해 주는 파트너입니다.

말투:
- 존댓말로 따뜻하고 차분하게. 과장·단정·공포 조장은 금지.
- 먼저 확인된 사실(숫자) → 그다음 근거 있는 해석 → 마지막에 불확실성.
- 이모지 금지.

할루시네이션 금지 (최우선):
1. WEALTH_CONTEXT의 holdings / macro_indicators / holding_moves / market_news / snapshots 숫자만 "사실"로 말하세요.
2. 상승·하락 "원인"은 반드시 (a) market_news 헤드라인, 또는 (b) Google 검색으로 확인된 정보에만 근거하세요.
3. 뉴스/검색에 없는 원인을 지어내지 마세요. 모르면 "확인된 원인은 아직 없어요. 지금은 가격 변동만 말씀드릴 수 있어요"라고 하세요.
4. 추측할 때는 반드시 "가설/가능성"이라고 명시하고, 사실과 분리하세요.
5. 개별 종목 매수·매도 권유, 세금 확정 자문은 하지 마세요.
6. 답변 끝에 사용한 근거를 짧게 적어 주세요. 예: "근거: 보유 시세 · 코스피 헤드라인 · 검색".

분석 방식:
- 보유 종목 질문 → holding_moves의 기간 수익률을 먼저 제시하고, 관련 뉴스/검색이 있으면 사유를 연결.
- 시장 전반 질문 → macro_indicators(+chg)와 market_news, 필요 시 검색으로 원인 정리.
- 포트폴리오와 시장을 비교할 때는 숫자로 대조하고, 인과는 근거가 있을 때만.

한국어로 답하고 숫자에는 단위(원/달러/%/포인트)를 붙이세요.`;

const UA = { "User-Agent": "Bujattung/1.0 (wealth-chat)" };

type MacroRow = {
  key: string;
  label: string;
  value: number | null;
  unit: string;
  source: string;
  updated_at: string | null;
  change_1d_pct?: number | null;
  change_5d_pct?: number | null;
  error?: string;
};

type MoveRow = {
  ticker: string;
  name: string | null;
  yahoo_symbol: string;
  price: number | null;
  currency: string | null;
  change_1d_pct: number | null;
  change_5d_pct: number | null;
  change_1m_pct: number | null;
  market_value: number | null;
  vs_avg_pct: number | null;
};

type NewsRow = {
  query: string;
  title: string;
  publisher: string | null;
  link: string | null;
  published_at: string | null;
};

function pctChange(from: number | null | undefined, to: number | null | undefined) {
  if (from == null || to == null || !Number.isFinite(from) || !Number.isFinite(to) || from === 0) {
    return null;
  }
  return ((to - from) / Math.abs(from)) * 100;
}

function lastFinite(arr: Array<number | null | undefined>): number | null {
  for (let i = arr.length - 1; i >= 0; i--) {
    const v = arr[i];
    if (v != null && Number.isFinite(v)) return Number(v);
  }
  return null;
}

function yahooSymbolForHolding(ticker: string): string {
  const t = String(ticker || "").trim().toUpperCase();
  if (/^\d{6}$/.test(t)) return `${t}.KS`;
  return t;
}

async function yahooChart(symbol: string, range = "1mo") {
  const url =
    `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}` +
    `?interval=1d&range=${encodeURIComponent(range)}`;
  const res = await fetch(url, { headers: UA });
  if (!res.ok) throw new Error(`Yahoo ${symbol} HTTP ${res.status}`);
  const payload = await res.json();
  const result = payload?.chart?.result?.[0];
  if (!result) throw new Error(`Yahoo ${symbol} empty`);
  const meta = result.meta ?? {};
  const closes: Array<number | null> = result.indicators?.quote?.[0]?.close ?? [];
  const price =
    meta.regularMarketPrice != null
      ? Number(meta.regularMarketPrice)
      : lastFinite(closes);
  const prevClose =
    meta.chartPreviousClose != null
      ? Number(meta.chartPreviousClose)
      : closes.length >= 2
        ? lastFinite(closes.slice(0, -1))
        : null;
  const close5 = closes.length >= 6 ? lastFinite(closes.slice(0, -5)) : lastFinite(closes);
  const close1m = lastFinite(closes.slice(0, 1)) ?? lastFinite(closes);
  return {
    price,
    currency: (meta.currency as string | undefined) ?? null,
    change_1d_pct: pctChange(prevClose, price),
    change_5d_pct: pctChange(close5, price),
    change_1m_pct: pctChange(close1m, price),
  };
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

async function frankfurterUsdKrwHistory(): Promise<{
  latest: number;
  change_1d_pct: number | null;
  change_5d_pct: number | null;
}> {
  const end = new Date();
  const start = new Date(end.getTime() - 10 * 86400000);
  const from = start.toISOString().slice(0, 10);
  const to = end.toISOString().slice(0, 10);
  const res = await fetch(
    `https://api.frankfurter.dev/v1/${from}..${to}?from=USD&to=KRW`
  );
  if (!res.ok) {
    const latest = await frankfurterUsdKrw();
    return { latest, change_1d_pct: null, change_5d_pct: null };
  }
  const data = await res.json();
  const rates = data?.rates || {};
  const dates = Object.keys(rates).sort();
  const values = dates.map((d) => Number(rates[d]?.KRW)).filter((n) => Number.isFinite(n));
  const latest = values.at(-1) ?? (await frankfurterUsdKrw());
  const d1 = values.length >= 2 ? values.at(-2)! : null;
  const d5 = values.length >= 6 ? values.at(-6)! : values[0] ?? null;
  return {
    latest,
    change_1d_pct: pctChange(d1, latest),
    change_5d_pct: pctChange(d5, latest),
  };
}

async function fetchMacroIndicators(): Promise<MacroRow[]> {
  const now = new Date().toISOString();
  const specs: {
    key: string;
    label: string;
    unit: string;
    source: string;
    run: () => Promise<{
      price: number;
      change_1d_pct: number | null;
      change_5d_pct: number | null;
    }>;
  }[] = [
    {
      key: "KOSPI",
      label: "코스피",
      unit: "pt",
      source: "Yahoo ^KS11",
      run: async () => await yahooChart("^KS11", "1mo"),
    },
    {
      key: "SP500",
      label: "S&P 500",
      unit: "pt",
      source: "Yahoo ^GSPC",
      run: async () => await yahooChart("^GSPC", "1mo"),
    },
    {
      key: "NASDAQ",
      label: "나스닥",
      unit: "pt",
      source: "Yahoo ^IXIC",
      run: async () => await yahooChart("^IXIC", "1mo"),
    },
    {
      key: "USDKRW",
      label: "원달러환율",
      unit: "KRW",
      source: "Frankfurter",
      run: async () => {
        const fx = await frankfurterUsdKrwHistory();
        return {
          price: fx.latest,
          change_1d_pct: fx.change_1d_pct,
          change_5d_pct: fx.change_5d_pct,
        };
      },
    },
    {
      key: "WTI",
      label: "WTI 국제유가",
      unit: "USD/bbl",
      source: "Yahoo CL=F",
      run: async () => await yahooChart("CL=F", "1mo"),
    },
    {
      key: "US_IRX",
      label: "미국 단기금리(13주 T-Bill)",
      unit: "%",
      source: "Yahoo ^IRX",
      run: async () => await yahooChart("^IRX", "1mo"),
    },
    {
      key: "US10Y",
      label: "미국 10년물 금리",
      unit: "%",
      source: "Yahoo ^TNX",
      run: async () => await yahooChart("^TNX", "1mo"),
    },
  ];

  return await Promise.all(
    specs.map(async (s) => {
      try {
        const r = await s.run();
        return {
          key: s.key,
          label: s.label,
          value: r.price,
          unit: s.unit,
          source: s.source,
          updated_at: now,
          change_1d_pct: r.change_1d_pct,
          change_5d_pct: r.change_5d_pct,
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
}

async function fetchHoldingMoves(
  holdings: Array<Record<string, unknown>>
): Promise<MoveRow[]> {
  const sorted = [...holdings].sort((a, b) => {
    const av = Number(a.market_value || 0);
    const bv = Number(b.market_value || 0);
    return bv - av;
  });
  const top = sorted.slice(0, 10);
  return await Promise.all(
    top.map(async (h) => {
      const ticker = String(h.ticker || "");
      const yahoo = yahooSymbolForHolding(ticker);
      try {
        const c = await yahooChart(yahoo, "1mo");
        return {
          ticker,
          name: (h.name as string | null) ?? null,
          yahoo_symbol: yahoo,
          price: c.price,
          currency: c.currency || String(h.currency || ""),
          change_1d_pct: c.change_1d_pct,
          change_5d_pct: c.change_5d_pct,
          change_1m_pct: c.change_1m_pct,
          market_value: h.market_value != null ? Number(h.market_value) : null,
          vs_avg_pct: h.return_pct != null ? Number(h.return_pct) : null,
        } satisfies MoveRow;
      } catch (e) {
        return {
          ticker,
          name: (h.name as string | null) ?? null,
          yahoo_symbol: yahoo,
          price: h.current_price != null ? Number(h.current_price) : null,
          currency: String(h.currency || ""),
          change_1d_pct: null,
          change_5d_pct: null,
          change_1m_pct: null,
          market_value: h.market_value != null ? Number(h.market_value) : null,
          vs_avg_pct: h.return_pct != null ? Number(h.return_pct) : null,
        } satisfies MoveRow;
      }
    })
  );
}

async function yahooNews(query: string, limit = 4): Promise<NewsRow[]> {
  const url =
    `https://query1.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(query)}` +
    `&newsCount=${limit}&quotesCount=0`;
  try {
    const res = await fetch(url, { headers: UA });
    if (!res.ok) return [];
    const data = await res.json();
    const news = Array.isArray(data?.news) ? data.news : [];
    return news.slice(0, limit).map((n: Record<string, unknown>) => ({
      query,
      title: String(n.title || "").trim(),
      publisher: n.publisher ? String(n.publisher) : null,
      link: n.link ? String(n.link) : null,
      published_at:
        typeof n.providerPublishTime === "number"
          ? new Date(n.providerPublishTime * 1000).toISOString()
          : null,
    })).filter((n: NewsRow) => n.title);
  } catch {
    return [];
  }
}

async function fetchMarketNews(moves: MoveRow[]): Promise<NewsRow[]> {
  const queries = [
    "KOSPI",
    "S&P 500",
    "USD KRW",
    "crude oil WTI",
    ...moves.slice(0, 6).map((m) => m.ticker),
  ];
  const batches = await Promise.all(queries.map((q) => yahooNews(q, 3)));
  const seen = new Set<string>();
  const out: NewsRow[] = [];
  for (const batch of batches) {
    for (const n of batch) {
      const key = n.title.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(n);
      if (out.length >= 24) return out;
    }
  }
  return out;
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
      currency: m.unit.includes("KRW")
        ? "KRW"
        : m.unit.includes("%")
          ? "PCT"
          : "USD",
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

function extractGroundingSources(data: Record<string, unknown>): {
  title: string;
  uri: string;
}[] {
  const cand = (data?.candidates as unknown[])?.[0] as
    | Record<string, unknown>
    | undefined;
  const meta = cand?.groundingMetadata as Record<string, unknown> | undefined;
  const chunks = (meta?.groundingChunks as unknown[]) || [];
  const out: { title: string; uri: string }[] = [];
  const seen = new Set<string>();
  for (const c of chunks) {
    const web = (c as { web?: { title?: string; uri?: string } })?.web;
    if (!web?.uri) continue;
    if (seen.has(web.uri)) continue;
    seen.add(web.uri);
    out.push({ title: web.title || web.uri, uri: web.uri });
    if (out.length >= 8) break;
  }
  return out;
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
      .limit(12),
    admin
      .from("market_index_snapshots")
      .select("snapshot_date,kospi,sp500,nasdaq,usdkrw")
      .order("snapshot_date", { ascending: false })
      .limit(7),
    fetchMacroIndicators(),
  ]);

  try {
    await persistMacros(admin, macros);
  } catch {
    /* ignore */
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

  const holding_moves = await fetchHoldingMoves(
    enriched as Array<Record<string, unknown>>
  );
  const market_news = await fetchMarketNews(holding_moves);

  const ctx = {
    holdings: enriched,
    holding_moves,
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
    market_news,
    analysis_rules: {
      facts: ["holdings", "holding_moves", "macro_indicators", "snapshots", "market_news"],
      causes_require: ["market_news", "google_search"],
      no_invention: true,
    },
    note:
      "holding_moves/macro_indicators는 실시간 시세, market_news는 Yahoo 헤드라인입니다. 원인 해석은 뉴스·검색 근거가 있을 때만 하세요.",
    recent_chat_logs: (chatLogs.data || []).reverse(),
    meta: {
      holdings: enriched.length,
      usdkrw,
      macros_ok: macros.filter((m) => m.value != null).length,
      moves_ok: holding_moves.filter((m) => m.change_1d_pct != null).length,
      news: market_news.length,
    },
  };

  let text = JSON.stringify(ctx);
  if (text.length > 18000) text = text.slice(0, 18000) + "…(truncated)";
  return { ctx, text };
}

async function callGemini(opts: {
  apiKey: string;
  model: string;
  turns: { role: string; parts: { text: string }[] }[];
  useSearch: boolean;
}) {
  const url =
    `https://generativelanguage.googleapis.com/v1beta/models/${opts.model}:generateContent?key=${opts.apiKey}`;
  const body: Record<string, unknown> = {
    systemInstruction: { parts: [{ text: WEALTH_CHAT_SYSTEM }] },
    contents: opts.turns,
    generationConfig: { temperature: 0.25 },
  };
  if (opts.useSearch) {
    body.tools = [{ google_search: {} }];
  }
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const raw = await res.text();
  if (!res.ok) {
    throw new Error(`Gemini ${res.status}: ${raw.slice(0, 400)}`);
  }
  return JSON.parse(raw) as Record<string, unknown>;
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
            `포트폴리오 숫자는 WEALTH_CONTEXT만 사용하세요. ` +
            `시장/종목 원인 분석이 필요하면 Google 검색 도구를 쓰고, 검색·뉴스로 확인되지 않은 원인은 말하지 마세요. ` +
            `준비되면 "준비됨"이라고만 답하세요.`,
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
    turns.push({
      role: "user",
      parts: [
        {
          text:
            `${message}\n\n` +
            `(원인·이슈를 말할 때는 검색/뉴스가 있을 때만. 없으면 가격 사실만.)`,
        },
      ],
    });

    const apiKey = Deno.env.get("GEMINI_API_KEY");
    if (!apiKey) throw new Error("GEMINI_API_KEY missing");
    const model = Deno.env.get("GEMINI_MODEL") ?? "gemini-2.5-flash";

    let data: Record<string, unknown>;
    let usedSearch = true;
    try {
      data = await callGemini({ apiKey, model, turns, useSearch: true });
    } catch (e) {
      // Fallback if search tool unsupported on this model/key
      usedSearch = false;
      data = await callGemini({ apiKey, model, turns, useSearch: false });
      if (!data) throw e;
    }

    const reply =
      data?.candidates?.[0] &&
      ((data.candidates as Array<{ content?: { parts?: Array<{ text?: string }> } }>)[0]
        .content?.parts?.map((p) => p.text ?? "")
        .join("")
        ?.trim() ||
        "");
    if (!reply) throw new Error("Empty Gemini reply");

    const sources = extractGroundingSources(data);
    let finalReply = reply;
    if (sources.length) {
      const lines = sources
        .slice(0, 5)
        .map((s, i) => `${i + 1}. ${s.title}`)
        .join("\n");
      if (!/근거|출처|검색/i.test(finalReply)) {
        finalReply = `${finalReply}\n\n참고 출처\n${lines}`;
      }
    }

    await supabase.from("ai_chat_logs").insert({
      user_id: user.id,
      user_query: message,
      ai_response: finalReply,
      context_summary: contextText.slice(0, 2000),
    });

    return json({
      ok: true,
      reply: finalReply,
      sources,
      meta: { ...ctx.meta, grounded_search: usedSearch, sources: sources.length },
    });
  } catch (e) {
    if (e instanceof Response) return e;
    return json(
      { ok: false, error: e instanceof Error ? e.message : "unknown" },
      500
    );
  }
});
