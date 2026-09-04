/** Yahoo chart dividend events → qty × DPS estimates (Toss / 한투 국내 ETF). */

import type { SupabaseClient } from "jsr:@supabase/supabase-js@2";
import { SYNC_REVISION } from "./syncRevision.ts";

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

function storedKrTicker(raw: unknown): string {
  let t = String(raw || "").trim().toUpperCase();
  if (!t) return t;
  if (t.endsWith(".KS") || t.endsWith(".KQ")) t = t.slice(0, -3);
  const aIdx = t.indexOf("A");
  if (aIdx >= 0 && /^\d*$/.test(t.slice(0, aIdx)) && /^\d+$/.test(t.slice(aIdx + 1))) {
    t = t.slice(aIdx + 1);
  }
  if (/^\d+$/.test(t) && t.length <= 6) return t.padStart(6, "0");
  if (/^\d+$/.test(t) && t.length > 6) return t.slice(-6);
  return t;
}

function lookbackDates(days: number): { fromDate: string; toDate: string } {
  const to = new Date();
  const from = new Date(to.getTime() - Math.max(1, days) * 86400000);
  return { fromDate: from.toISOString().slice(0, 10), toDate: to.toISOString().slice(0, 10) };
}

export async function normalizeStoredDividendTickers(
  admin: SupabaseClient,
  accountIds?: string[]
): Promise<number> {
  let query = admin.from("dividends").select("id,ticker");
  if (accountIds?.length) query = query.in("account_id", accountIds);
  const { data, error } = await query.limit(2000);
  if (error || !data?.length) return 0;
  let n = 0;
  for (const row of data) {
    const next = storedKrTicker(row.ticker);
    if (!next || next === row.ticker) continue;
    const { error: upd } = await admin.from("dividends").update({ ticker: next }).eq("id", row.id);
    if (!upd) n += 1;
  }
  return n;
}

export async function upsertEstimatedDividendsForInstitution(
  admin: SupabaseClient,
  opts: {
    userId: string;
    institution: string;
    source: "toss" | "kis";
    lookbackDays?: number;
  }
): Promise<{ inserted: number; total: number; normalized: number; sync_revision: string }> {
  const { data: accounts } = await admin
    .from("accounts")
    .select("id,currency,user_id")
    .eq("institution", opts.institution);
  const accountRows = accounts || [];
  const accountIds = accountRows.map((a) => String(a.id));
  const normalized = await normalizeStoredDividendTickers(admin, accountIds);
  if (!accountIds.length) {
    return { inserted: 0, total: 0, normalized, sync_revision: SYNC_REVISION };
  }

  const { data: holdings } = await admin
    .from("holdings")
    .select("ticker,name,quantity,currency,account_id")
    .in("account_id", accountIds);

  const byAccount = new Map<string, YahooHolding[]>();
  for (const h of holdings || []) {
    const aid = String(h.account_id || "");
    if (!aid) continue;
    const list = byAccount.get(aid) || [];
    list.push({
      ticker: storedKrTicker(h.ticker) || String(h.ticker || "").trim(),
      name: String(h.name || h.ticker || "").trim(),
      quantity: Number(h.quantity || 0),
      currency: String(h.currency || "KRW"),
    });
    byAccount.set(aid, list);
  }

  const dates = lookbackDates(opts.lookbackDays ?? 365);
  const known = new Set<string>();
  const { data: existing } = await admin
    .from("dividends")
    .select("external_id")
    .in("account_id", accountIds);
  for (const row of existing || []) {
    const ext = String(row.external_id || "").trim();
    if (ext) known.add(ext);
  }

  const accountUser = new Map(accountRows.map((a) => [String(a.id), String(a.user_id || "")]));
  let inserted = 0;
  for (const [accountId, rows] of byAccount) {
    if (!rows.length) continue;
    let estimated: EstimatedDividend[] = [];
    try {
      estimated = await estimateHoldingDividends(rows, { ...dates, source: opts.source });
    } catch (e) {
      console.log("yahoo estimate skip", opts.institution, accountId, e);
      continue;
    }
    const userId = accountUser.get(accountId) || opts.userId;
    for (const row of estimated) {
      if (known.has(row.external_id)) continue;
      const ticker = storedKrTicker(row.ticker) || row.ticker;
      const { data, error } = await admin
        .from("dividends")
        .insert({
          user_id: userId,
          account_id: accountId,
          ticker,
          name: row.name || ticker,
          pay_date: row.pay_date,
          amount: row.amount,
          currency: row.currency,
          memo: row.memo,
          external_id: row.external_id,
        })
        .select("id");
      if (error || !data?.length) continue;
      known.add(row.external_id);
      inserted += 1;
    }
  }

  const { count } = await admin
    .from("dividends")
    .select("id", { count: "exact", head: true })
    .in("account_id", accountIds);
  return {
    inserted,
    total: count || 0,
    normalized,
    sync_revision: SYNC_REVISION,
  };
}
