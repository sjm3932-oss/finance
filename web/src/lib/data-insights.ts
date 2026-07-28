import { createClient } from "@/lib/supabase/server";
import {
  PeriodChange,
  HoldingSnapRow,
  RealizedRow,
  DividendRow,
  FlowRow,
  IndexSnap,
  PNL_KIND_KO,
  periodChangeStats,
  toKrwAmount,
  dividendStats,
  normalizeSeries,
} from "@/lib/insights";
import type { DailySnap, DebtRow } from "@/lib/portfolio";

async function safeSelect<T>(
  run: () => PromiseLike<{ data: T[] | null; error: { message: string } | null }>
): Promise<T[]> {
  try {
    const { data, error } = await run();
    if (error) return [];
    return data || [];
  } catch {
    return [];
  }
}

export async function loadHoldingSnaps(days = 90): Promise<HoldingSnapRow[]> {
  const supabase = await createClient();
  const since = new Date();
  since.setDate(since.getDate() - days);
  return safeSelect<HoldingSnapRow>(() =>
    supabase
      .from("holding_daily_snapshots")
      .select("snapshot_date,account_id,ticker,market_value_krw")
      .gte("snapshot_date", since.toISOString().slice(0, 10))
      .order("snapshot_date")
  );
}

export async function loadPeriodChange(
  liveInvestKrw: number,
  accountIds: string[] | null
): Promise<PeriodChange> {
  const snaps = await loadHoldingSnaps(40);
  return periodChangeStats(liveInvestKrw, snaps, accountIds);
}

export async function loadIndexSnaps(days = 400): Promise<IndexSnap[]> {
  const supabase = await createClient();
  const since = new Date();
  since.setDate(since.getDate() - days);
  return safeSelect<IndexSnap>(() =>
    supabase
      .from("market_index_snapshots")
      .select("snapshot_date,nasdaq,sp500,kospi")
      .gte("snapshot_date", since.toISOString().slice(0, 10))
      .order("snapshot_date")
  );
}

export async function loadBenchmarkSeries(
  snaps: DailySnap[],
  indexKey: "sp500" | "nasdaq" | "kospi" = "sp500"
) {
  const indexes = await loadIndexSnaps(400);
  const port = snaps
    .filter((s) => s.total_investment != null || s.net_assets != null)
    .map((s) => ({
      date: String(s.snapshot_date).slice(0, 10),
      value: Number(s.total_investment ?? s.net_assets ?? 0),
    }))
    .filter((p) => p.value > 0);
  const idx = indexes
    .map((s) => ({
      date: String(s.snapshot_date).slice(0, 10),
      value: Number(s[indexKey] ?? 0),
    }))
    .filter((p) => p.value > 0);

  const dates = port.map((p) => p.date).filter((d) => idx.some((i) => i.date === d));
  const portAligned = port.filter((p) => dates.includes(p.date));
  const idxAligned = dates
    .map((d) => idx.find((i) => i.date === d)!)
    .filter(Boolean);

  return {
    portfolio: normalizeSeries(portAligned),
    index: normalizeSeries(idxAligned),
    indexKey,
  };
}

export async function loadRealizedRows(
  usdkrw: number | null,
  accountIds: string[] | null
): Promise<RealizedRow[]> {
  const supabase = await createClient();
  const rows: RealizedRow[] = [];

  const [tradesAll, dividendsAll, cash] = await Promise.all([
    safeSelect<{
      trade_date: string;
      ticker: string;
      realized_pnl: number | null;
      currency: string | null;
      account_id: string;
      quantity: number | null;
      price: number | null;
      trade_type: string;
    }>(() =>
      supabase
        .from("trades")
        .select(
          "trade_date,ticker,realized_pnl,currency,account_id,quantity,price,trade_type"
        )
        .eq("trade_type", "sell")
        .not("realized_pnl", "is", null)
        .order("trade_date", { ascending: false })
        .limit(500)
    ),
    safeSelect<{
      pay_date: string;
      ticker: string;
      name: string | null;
      amount: number;
      currency: string | null;
      account_id: string | null;
    }>(() =>
      supabase
        .from("dividends")
        .select("pay_date,ticker,name,amount,currency,account_id")
        .order("pay_date", { ascending: false })
        .limit(500)
    ),
    safeSelect<{
      flow_date: string;
      category: string | null;
      amount: number;
      currency: string | null;
      account_id: string | null;
      flow_type: string;
    }>(() =>
      supabase
        .from("cash_flows")
        .select("flow_date,category,amount,currency,account_id,flow_type")
        .eq("flow_type", "income")
        .limit(300)
    ),
  ]);

  let trades = tradesAll;
  if (accountIds) {
    trades = trades.filter((t) => accountIds.includes(t.account_id));
  }
  for (const t of trades) {
    const pnl = Number(t.realized_pnl || 0);
    const ccy = t.currency || "KRW";
    rows.push({
      event_date: String(t.trade_date).slice(0, 10),
      pnl_kind: "trade_realized",
      pnl_kind_ko: PNL_KIND_KO.trade_realized,
      asset_ref: t.ticker,
      asset_name: t.ticker,
      pnl,
      currency: ccy,
      pnl_krw: toKrwAmount(pnl, ccy, usdkrw),
      account_id: t.account_id,
      detail: `매도 ${t.quantity ?? ""} @ ${t.price ?? ""}`,
    });
  }

  let dividends = dividendsAll;
  if (accountIds) {
    dividends = dividends.filter(
      (d) => d.account_id && accountIds.includes(d.account_id)
    );
  }
  for (const d of dividends) {
    const amount = Number(d.amount || 0);
    const ccy = d.currency || "KRW";
    rows.push({
      event_date: String(d.pay_date).slice(0, 10),
      pnl_kind: "dividend",
      pnl_kind_ko: PNL_KIND_KO.dividend,
      asset_ref: d.ticker,
      asset_name: d.name || d.ticker,
      pnl: amount,
      currency: ccy,
      pnl_krw: toKrwAmount(amount, ccy, usdkrw),
      account_id: d.account_id,
      detail: "배당",
    });
  }

  for (const c of cash) {
    if (!(c.category || "").includes("이자")) continue;
    if (accountIds && c.account_id && !accountIds.includes(c.account_id)) {
      continue;
    }
    if (accountIds && !c.account_id) continue;
    const amount = Number(c.amount || 0);
    const ccy = c.currency || "KRW";
    rows.push({
      event_date: String(c.flow_date).slice(0, 10),
      pnl_kind: "interest_income",
      pnl_kind_ko: PNL_KIND_KO.interest_income,
      asset_ref: c.category || "이자",
      asset_name: c.category || "이자",
      pnl: amount,
      currency: ccy,
      pnl_krw: toKrwAmount(amount, ccy, usdkrw),
      account_id: c.account_id,
      detail: "이자수입",
    });
  }

  return rows.sort((a, b) => b.event_date.localeCompare(a.event_date));
}

export async function loadDividends(
  accountIds: string[] | null
): Promise<DividendRow[]> {
  const supabase = await createClient();
  let rows = await safeSelect<DividendRow>(() =>
    supabase
      .from("dividends")
      .select("id,pay_date,ticker,name,amount,currency,account_id,memo")
      .order("pay_date", { ascending: false })
      .limit(500)
  );
  if (accountIds) {
    rows = rows.filter((d) => d.account_id && accountIds.includes(d.account_id));
  }
  return rows;
}

export async function loadDividendInsights(
  usdkrw: number | null,
  accountIds: string[] | null
) {
  const rows = await loadDividends(accountIds);
  return { rows, stats: dividendStats(rows, usdkrw) };
}

export async function loadAssetFlows(
  accountIds: string[] | null
): Promise<FlowRow[]> {
  const supabase = await createClient();
  let rows = await safeSelect<FlowRow>(() =>
    supabase
      .from("v_asset_flows")
      .select(
        "event_date,flow_kind,flow_subtype,asset_ref,amount,currency,memo,account_id"
      )
      .order("event_date", { ascending: false })
      .limit(500)
  );
  if (!rows.length) {
    // Fallback without view
    return [];
  }
  if (accountIds) {
    rows = rows.filter(
      (r) => r.account_id && accountIds.includes(r.account_id)
    );
  }
  return rows;
}

export async function loadTickerHistory(ticker: string, accountIds: string[] | null) {
  const supabase = await createClient();
  let trades = await safeSelect<Record<string, unknown>>(() =>
    supabase
      .from("trades")
      .select(
        "trade_date,trade_type,price,quantity,fee,currency,realized_pnl,reason,account_id"
      )
      .eq("ticker", ticker)
      .order("trade_date", { ascending: false })
      .limit(200)
  );
  let dividends = await safeSelect<DividendRow>(() =>
    supabase
      .from("dividends")
      .select("pay_date,ticker,name,amount,currency,account_id,memo")
      .eq("ticker", ticker)
      .order("pay_date", { ascending: false })
      .limit(200)
  );
  let snaps = await safeSelect<{
    snapshot_date: string;
    market_value_krw: number | null;
    account_id: string;
  }>(() =>
    supabase
      .from("holding_daily_snapshots")
      .select("snapshot_date,market_value_krw,account_id")
      .eq("ticker", ticker)
      .order("snapshot_date")
      .limit(365)
  );

  if (accountIds) {
    trades = trades.filter((t) =>
      accountIds.includes(String(t.account_id || ""))
    );
    dividends = dividends.filter(
      (d) => d.account_id && accountIds.includes(d.account_id)
    );
    snaps = snaps.filter((s) => accountIds.includes(s.account_id));
  }

  const valueSeries = new Map<string, number>();
  for (const s of snaps) {
    const d = String(s.snapshot_date).slice(0, 10);
    valueSeries.set(d, (valueSeries.get(d) || 0) + Number(s.market_value_krw || 0));
  }

  return {
    trades,
    dividends,
    valueTrend: [...valueSeries.entries()]
      .map(([date, value]) => ({ date, value }))
      .sort((a, b) => a.date.localeCompare(b.date)),
  };
}

export async function loadDebtDashboard(accountIds: string[] | null) {
  const supabase = await createClient();
  let debts = await safeSelect<
    DebtRow & {
      original_principal?: number | null;
      memo?: string | null;
      account_id?: string | null;
    }
  >(() =>
    supabase
      .from("debts")
      .select(
        "id,lender,principal,due_date,ownership,interest_rate,debt_kind,original_principal,memo,account_id"
      )
  );
  if (accountIds) {
    debts = debts.filter(
      (d) => !d.account_id || accountIds.includes(d.account_id)
    );
  }

  const debtIds = debts.map((d) => d.id).filter(Boolean) as string[];
  let txs: Record<string, unknown>[] = [];
  if (debtIds.length) {
    txs = await safeSelect(() =>
      supabase
        .from("debt_transactions")
        .select(
          "debt_id,tx_date,tx_type,amount,interest_portion,principal_portion,balance_before,balance_after,rate_used,memo"
        )
        .in("debt_id", debtIds)
        .order("tx_date", { ascending: false })
        .limit(200)
    );
  }

  const total = debts.reduce((s, d) => s + Number(d.principal || 0), 0);
  const orig = debts.reduce(
    (s, d) => s + Number(d.original_principal ?? d.principal ?? 0),
    0
  );
  const byKind = new Map<string, number>();
  for (const d of debts) {
    const k = d.debt_kind || "other";
    byKind.set(k, (byKind.get(k) || 0) + Number(d.principal || 0));
  }

  return {
    debts,
    txs,
    total,
    original: orig,
    repaid: Math.max(0, orig - total),
    byKind: [...byKind.entries()].map(([kind, value]) => ({ kind, value })),
  };
}

export async function loadWatchlist() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { items: [], alerts: [] };

  const items = await safeSelect<{
    id: string;
    ticker: string;
    name: string | null;
    target_price: number | null;
    stop_price: number | null;
    note: string | null;
  }>(() =>
    supabase
      .from("watchlist")
      .select("id,ticker,name,target_price,stop_price,note")
      .eq("user_id", user.id)
      .order("created_at", { ascending: false })
  );

  const prices = await safeSelect<{
    ticker: string;
    price: number;
    currency: string | null;
  }>(() =>
    supabase.from("market_prices").select("ticker,price,currency")
  );
  const pmap = new Map(prices.map((p) => [p.ticker, p]));

  const alerts = await safeSelect<{
    id: string;
    ticker: string;
    alert_kind: string;
    trigger_price: number | null;
    market_price: number | null;
  }>(() =>
    supabase
      .from("price_alert_events")
      .select("id,ticker,alert_kind,trigger_price,market_price")
      .eq("acknowledged", false)
      .order("created_at", { ascending: false })
      .limit(20)
  );

  return {
    items: items.map((it) => ({
      ...it,
      price: pmap.get(it.ticker)?.price ?? null,
      currency: pmap.get(it.ticker)?.currency ?? null,
    })),
    alerts,
  };
}

export async function loadTaxYear(year?: number) {
  const supabase = await createClient();
  const y = year || new Date().getFullYear();
  const rows = await safeSelect<{
    tax_year: number;
    taxable_gain: number | null;
    estimated_tax: number | null;
    cum_capital_gain?: number | null;
    tax_threshold?: number | null;
    dividend_tax?: number | null;
  }>(() =>
    supabase.from("v_tax_calculation").select("*").eq("tax_year", y)
  );
  if (rows.length) return { year: y, row: rows[0] };

  const rec = await safeSelect<{
    tax_year: number;
    cum_capital_gain: number | null;
    tax_threshold: number | null;
    dividend_tax: number | null;
  }>(() =>
    supabase.from("tax_records").select("*").eq("tax_year", y)
  );
  if (!rec.length) return { year: y, row: null };
  const r = rec[0];
  const gain = Math.max(
    0,
    Number(r.cum_capital_gain || 0) - Number(r.tax_threshold || 0)
  );
  return {
    year: y,
    row: {
      tax_year: y,
      taxable_gain: gain,
      estimated_tax: gain * 0.22,
      cum_capital_gain: r.cum_capital_gain,
      tax_threshold: r.tax_threshold,
      dividend_tax: r.dividend_tax,
    },
  };
}

export { dividendStats };
