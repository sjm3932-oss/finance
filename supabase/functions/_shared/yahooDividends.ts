/** Yahoo chart dividend events → qty × DPS estimates (Toss / 한투 국내 ETF). */

const YAHOO_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36";
const SKIP_TICKERS = new Set(["ISA-FUND"]);

export type YahooHolding = {
  ticker: string;
  name: string;
  quantity: number;
  currency: string;
};

export type EstimatedDividend = {
  external_id: string;
  ticker: string;
  name: string;
  pay_date: string;
  amount: number;
  currency: string;
  memo: string;
};

export function yahooChartSymbols(ticker: string): string[] {
  const t = String(ticker || "").trim().toUpperCase();
  if (/^\d+$/.test(t) && t.length <= 6) {
    const padded = t.padStart(6, "0");
    return [`${padded}.KS`, `${padded}.KQ`];
  }
  return [t];
}

export function parseYahooDividends(
  payload: unknown,
  opts: { ticker: string; quantity: number; start: string; end: string; source?: "toss" | "kis" }
): EstimatedDividend[] {
  if (opts.quantity <= 0) return [];
  const root = payload as { chart?: { result?: Array<{ events?: { dividends?: Record<string, { date?: number; amount?: number } } | Array<{ date?: number; amount?: number }> } }> } };
  const result = root?.chart?.result || [];
  if (!result.length) return [];
  const events = result[0]?.events?.dividends || {};
  const items = Array.isArray(events) ? events : Object.values(events);
  const source = opts.source || "toss";
  const idPrefix = source === "kis" ? "kis:div:est" : "toss:div";
  const memo = source === "kis" ? "한투 배당(추정)" : "토스 배당(추정)";
  const out: EstimatedDividend[] = [];
  for (const item of items) {
    if (!item || typeof item !== "object") continue;
    const dps = Number(item.amount || 0);
    const ts = item.date;
    if (!(dps > 0) || ts == null) continue;
    const payDate = new Date(Number(ts) * 1000).toISOString().slice(0, 10);
    if (payDate < opts.start || payDate > opts.end) continue;
    const amount = Math.round(dps * opts.quantity * 1e6) / 1e6;
    if (!(amount > 0)) continue;
    out.push({
      external_id: `${idPrefix}:${opts.ticker}:${payDate}:${dps.toFixed(6)}`,
      ticker: opts.ticker,
      name: opts.ticker,
      pay_date: payDate,
      amount,
      currency: /^\d+$/.test(String(opts.ticker)) ? "KRW" : "USD",
      memo,
    });
  }
  return out;
}

async function fetchYahooChart(symbol: string, fromDate: string, toDate: string): Promise<unknown> {
  const startTs = Math.floor(Date.parse(`${fromDate}T00:00:00Z`) / 1000);
  const endTs = Math.floor(Date.parse(`${toDate}T00:00:00Z`) / 1000) + 2 * 86400;
  const query = new URLSearchParams({
    interval: "1d",
    period1: String(startTs),
    period2: String(endTs),
    events: "div",
  });
  let last: unknown = {};
  for (const host of ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]) {
    const url = `https://${host}/v8/finance/chart/${encodeURIComponent(symbol)}?${query}`;
    try {
      const res = await fetch(url, { headers: { "User-Agent": YAHOO_UA, Accept: "application/json" } });
      if (!res.ok) continue;
      const payload = await res.json();
      last = payload;
      const events = payload?.chart?.result?.[0]?.events?.dividends;
      if (events && (Array.isArray(events) ? events.length : Object.keys(events).length)) return payload;
    } catch {
      continue;
    }
  }
  return last;
}

export async function estimateHoldingDividends(
  holdings: YahooHolding[],
  opts: { fromDate: string; toDate: string; source?: "toss" | "kis" }
): Promise<EstimatedDividend[]> {
  const cache = new Map<string, unknown>();
  const out: EstimatedDividend[] = [];
  const source = opts.source || "toss";
  for (const h of holdings) {
    const ticker = String(h.ticker || "").trim();
    const qty = Number(h.quantity || 0);
    if (!ticker || qty <= 0 || SKIP_TICKERS.has(ticker.toUpperCase())) continue;
    let payload: unknown;
    for (const symbol of yahooChartSymbols(ticker)) {
      if (!cache.has(symbol)) {
        payload = await fetchYahooChart(symbol, opts.fromDate, opts.toDate);
        cache.set(symbol, payload);
      } else {
        payload = cache.get(symbol);
      }
      const events = (payload as { chart?: { result?: Array<{ events?: { dividends?: unknown } }> } })
        ?.chart?.result?.[0]?.events?.dividends;
      if (events) break;
    }
    const rows = parseYahooDividends(payload, {
      ticker,
      quantity: qty,
      start: opts.fromDate,
      end: opts.toDate,
      source,
    });
    const ccy = String(h.currency || "").toUpperCase();
    const name = String(h.name || ticker).trim() || ticker;
    for (const row of rows) {
      if (ccy === "KRW" || ccy === "USD") row.currency = ccy;
      row.name = name;
      out.push(row);
    }
  }
  return out;
}

export function mergeEstimatedDividends<T extends { ticker: string; pay_date: string }>(
  broker: T[],
  estimated: T[]
): T[] {
  const have = new Set(broker.map((row) => `${row.ticker}|${row.pay_date}`));
  const out = [...broker];
  for (const row of estimated) {
    const key = `${row.ticker}|${row.pay_date}`;
    if (!row.ticker || !row.pay_date || have.has(key)) continue;
    out.push(row);
    have.add(key);
  }
  return out;
}
