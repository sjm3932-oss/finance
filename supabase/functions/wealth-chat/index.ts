// Wealth chat: portfolio DB + live macros/moves/news + Gemini Google Search grounding
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import {
  corsHeaders,
  json,
  requireUser,
  serviceClient,
} from "../_shared/gemini.ts";

const WEALTH_CHAT_SYSTEM = `당신은 부자뚱의 생활밀착형 자산 선생님입니다.
정명·지수가 일상에서 묻는 돈 고민(투자·연금·세금·대출·현금·환율·시세)을
일반인도 바로 이해하게, 쉽고 짧게 설명해 주세요.

대상 수준:
- 전문 용어는 필요할 때만 쓰고, 바로 쉬운 말로 풀어 주세요.
- 한 번에 세 가지 핵심만. 장문 강의·법령 조문 나열은 피하세요.
- "왜 중요한지 → 우리 숫자로는 어떤지 → 다음에 보면 좋은 점" 순서를 기본으로 하세요.
- 어려운 질문도 초등~중학생에게 설명하듯 친절하게, 그러나 존댓말로.

다룰 수 있는 주제 (가정 재무 전반):
- 보유 주식/ETF, 순자산, 손익, 배당, 환율
- 연금·보험·예적금 등 기타자산
- 세금(해외주식 양도·배당세 추정 등) — DB 수치 + 일반 개념 설명
- 대출/이자/원리금 계산, 상환 여력에 대한 쉬운 설명
- 시장 지표(코스피, S&P, 나스닥, 원달러, 유가, 금리)와 보유와의 연결
- "이게 뭐예요?" 식의 개념 질문(ISA, IRP, 중도상환수수료 등) — 검색으로 최신·일반 정보를 확인한 뒤 쉽게 설명

말투:
- 존댓말, 따뜻하고 차분. 이모지 금지. 공포·단정 금지.
- 계산을 보여줄 때는 식보다 "한 달에 이자가 대략 ○○원"처럼 결과 중심으로.

할루시네이션 금지:
1. 정명·지수의 금액·잔금·보유·세금 숫자는 WEALTH_CONTEXT만 사실로 쓰세요.
2. 시장/종목 "왜 올랐/내렸"은 market_news 또는 Google 검색 근거가 있을 때만.
3. 일반 제도·개념(연금저축, 과세, 대출 용어)은 검색으로 확인한 범위에서만, 쉽게 설명하세요.
4. 모르는 개인 숫자나 없는 계좌를 만들어내지 마세요. 없으면 "기록에 없어요. 기록 탭에 넣으면 계산해 드릴게요"라고 하세요.
5. 특정 종목 매수·매도 권유, "이 세금이 확정" 같은 단정은 금지. 추정은 "참고용 추정"이라고 밝히세요.
6. 답 끝에 근거를 한 줄로: 예) "근거: 부채 잔금 · 세금 기록 · 검색".

계산 안내:
- loan_helpers / tax / debts / other_assets 가 있으면 그 숫자로 먼저 계산·설명하세요.
- 사용자가 가정(예: 매달 100만 원 상환)을 주면, 그 가정임을 밝히고 대략 계산해 주세요.`;

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

function splitMonthlyPayment(
  balance: number,
  annualRatePct: number,
  payment: number
) {
  const bal = Math.max(0, Number(balance) || 0);
  const pay = Math.max(0, Number(payment) || 0);
  const interest = Math.round((bal * (Number(annualRatePct) || 0)) / 100 / 12);
  if (pay <= interest) return { interest: pay, principal: 0, leftover_interest: interest - pay };
  const principal = Math.min(bal, pay - interest);
  return { interest, principal, leftover_interest: 0 };
}

function buildLoanHelpers(debts: Array<Record<string, unknown>>) {
  return debts.map((d) => {
    const principal = Number(d.principal || 0);
    const rate = Number(d.interest_rate || 0);
    const monthlyInterest = Math.round((principal * rate) / 100 / 12);
    const samplePay = Math.max(monthlyInterest + 100000, Math.round(principal * 0.01));
    const split = splitMonthlyPayment(principal, rate, samplePay);
    const original = Number(d.original_principal || 0);
    return {
      id: d.id,
      lender: d.lender,
      debt_kind: d.debt_kind,
      principal,
      interest_rate_pct: rate,
      due_date: d.due_date ?? null,
      ownership: d.ownership ?? null,
      approx_monthly_interest_krw: monthlyInterest,
      example_payment_krw: samplePay,
      example_split: split,
      repaid_if_original_known:
        original > 0 ? Math.max(0, original - principal) : null,
      plain:
        `${d.lender || "대출"} 잔금 ${principal.toLocaleString("ko-KR")}원, ` +
        `연 ${rate}%면 한 달 이자만 대략 ${monthlyInterest.toLocaleString("ko-KR")}원 수준입니다.`,
    };
  });
}

function buildTaxPlain(taxRows: Array<Record<string, unknown>>) {
  return taxRows.map((t) => {
    const year = t.tax_year;
    const cum = Number(t.cum_capital_gain ?? t.taxable_gain ?? 0);
    const threshold = Number(t.tax_threshold ?? 2_500_000);
    const div = Number(t.dividend_tax ?? 0);
    const taxable = Math.max(0, cum - threshold);
    const estimated = t.estimated_tax != null ? Number(t.estimated_tax) : taxable * 0.22;
    return {
      tax_year: year,
      cum_capital_gain: cum,
      tax_threshold: threshold,
      dividend_tax: div,
      estimated_capital_gains_tax: estimated,
      plain:
        `${year}년 기준, 누적 양도차익 약 ${cum.toLocaleString("ko-KR")}원에서 ` +
        `기본공제 ${threshold.toLocaleString("ko-KR")}원을 빼면 과세표준 느낌의 금액이 ` +
        `${taxable.toLocaleString("ko-KR")}원이고, 단순 22%로 보면 양도세 추정이 ` +
        `약 ${Math.round(estimated).toLocaleString("ko-KR")}원입니다. (참고용)`,
    };
  });
}

function buildOtherAssetsPlain(rows: Array<Record<string, unknown>>) {
  const kindKo: Record<string, string> = {
    real_estate: "부동산",
    pension: "연금",
    insurance: "보험",
    deposit: "예적금",
    crypto: "암호화폐",
    other: "기타",
  };
  return rows.map((r) => ({
    name: r.name,
    kind: r.asset_kind,
    kind_ko: kindKo[String(r.asset_kind || "")] || String(r.asset_kind || "기타"),
    value_krw: Number(r.value_krw || 0),
    ownership: r.ownership,
    memo: r.memo ?? null,
    plain: `${r.name || "항목"}(${kindKo[String(r.asset_kind || "")] || "기타"}) 평가액 ${Number(r.value_krw || 0).toLocaleString("ko-KR")}원`,
  }));
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
    taxRecords,
    portfolio,
    dividends,
    otherAssets,
    debtTxs,
    chatLogs,
    indexSnaps,
    macros,
  ] = await Promise.all([
    admin.from("holdings").select("*"),
    admin.from("market_prices").select("*"),
    admin
      .from("accounts")
      .select("id,institution,account_type,currency,ownership,cash_balance"),
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
    admin.from("tax_records").select("*"),
    admin.from("v_portfolio").select("*"),
    admin
      .from("dividends")
      .select("pay_date,ticker,amount,currency,memo")
      .order("pay_date", { ascending: false })
      .limit(30),
    admin.from("other_assets").select("*"),
    admin
      .from("debt_transactions")
      .select("tx_date,tx_type,amount,memo,debt_id")
      .order("tx_date", { ascending: false })
      .limit(20),
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

  const debtRows = (debts.data || []) as Array<Record<string, unknown>>;
  const otherRows = (otherAssets.data || []) as Array<Record<string, unknown>>;
  const taxRows = (
    (taxView.data || []).length ? taxView.data : taxRecords.data || []
  ) as Array<Record<string, unknown>>;

  const loan_helpers = buildLoanHelpers(debtRows);
  const tax_plain = buildTaxPlain(taxRows);
  const other_assets_plain = buildOtherAssetsPlain(otherRows);

  const invest = enriched.reduce((s, h) => s + (h.market_value || 0), 0);
  const cash = ((accounts.data || []) as Array<Record<string, unknown>>).reduce(
    (s, a) => s + Number(a.cash_balance || 0),
    0
  );
  const otherSum = otherRows.reduce((s, r) => s + Number(r.value_krw || 0), 0);
  const debtSum = debtRows.reduce((s, d) => s + Number(d.principal || 0), 0);
  const pensionSum = otherRows
    .filter((r) => String(r.asset_kind) === "pension")
    .reduce((s, r) => s + Number(r.value_krw || 0), 0);

  const household_summary = {
    invest_krw_approx: invest,
    cash_krw_approx: cash,
    other_assets_krw: otherSum,
    pension_krw: pensionSum,
    debt_krw: debtSum,
    net_worth_approx: invest + cash + otherSum - debtSum,
    plain:
      `대략 투자 ${Math.round(invest).toLocaleString("ko-KR")}원 + 현금 ${Math.round(cash).toLocaleString("ko-KR")}원 ` +
      `+ 기타(연금 등) ${Math.round(otherSum).toLocaleString("ko-KR")}원 − 부채 ${Math.round(debtSum).toLocaleString("ko-KR")}원 ` +
      `→ 순자산 약 ${Math.round(invest + cash + otherSum - debtSum).toLocaleString("ko-KR")}원 수준입니다.`,
  };

  const holding_moves = await fetchHoldingMoves(
    enriched as Array<Record<string, unknown>>
  );
  const market_news = await fetchMarketNews(holding_moves);

  const ctx = {
    household_summary,
    holdings: enriched,
    holding_moves,
    accounts: accounts.data || [],
    debts: debtRows,
    loan_helpers,
    other_assets: otherRows,
    other_assets_plain,
    recent_debt_transactions: debtTxs.data || [],
    recent_trades: trades.data || [],
    recent_snapshots: snaps.data || [],
    tax: taxRows,
    tax_plain,
    portfolio: (portfolio.data || []).slice(0, 40),
    dividends: dividends.data || [],
    usdkrw,
    macro_indicators: macros,
    recent_index_snapshots: indexSnaps.data || [],
    market_news,
    analysis_rules: {
      facts: [
        "household_summary",
        "holdings",
        "holding_moves",
        "loan_helpers",
        "tax_plain",
        "other_assets_plain",
        "macro_indicators",
        "snapshots",
        "market_news",
      ],
      teaching: ["연금", "세금", "대출", "환율", "시세", "순자산"],
      causes_require: ["market_news", "google_search"],
      no_invention: true,
      audience: "일반인 · 쉬운 설명",
    },
    note:
      "숫자는 DB·실시간 시세 기준. 제도/개념은 검색으로 확인 후 쉽게 설명. 원인 해석은 뉴스·검색 근거가 있을 때만.",
    recent_chat_logs: (chatLogs.data || []).reverse(),
    meta: {
      holdings: enriched.length,
      debts: debtRows.length,
      other_assets: otherRows.length,
      usdkrw,
      macros_ok: macros.filter((m) => m.value != null).length,
      moves_ok: holding_moves.filter((m) => m.change_1d_pct != null).length,
      news: market_news.length,
    },
  };

  let text = JSON.stringify(ctx);
  if (text.length > 20000) text = text.slice(0, 20000) + "…(truncated)";
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
            `포트폴리오·부채·세금·연금 숫자는 WEALTH_CONTEXT만 사용하세요. ` +
            `개념 설명·시장 원인은 Google 검색으로 확인하고, 일반인도 이해하게 쉽게 가르치세요. ` +
            `확인 안 된 숫자/원인은 만들지 마세요. 준비되면 "준비됨"이라고만 답하세요.`,
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
            `(쉬운 설명으로. 우리 집 숫자는 컨텍스트, 개념·시세 원인은 검색/뉴스 근거가 있을 때만.)`,
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
