// Supabase Edge Function: refresh prices into market_prices
// Korean 6-digit tickers → Naver, others → Yahoo; FX via Frankfurter
// Also backfills holdings.name from the quote APIs.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const PRIVATE = new Set(["SPACEX", "PRIVATE"]);
const UA = { "User-Agent": "Bujattung/1.0" };

function normalizeTicker(raw: unknown): string {
  let t = String(raw || "").trim().toUpperCase();
  if (t.endsWith(".KS") || t.endsWith(".KQ")) {
    const base = t.slice(0, -3);
    if (/^\d{6}$/.test(base)) return base;
  }
  return t;
}

function isKoreanTicker(ticker: string): boolean {
  return /^\d{6}$/.test(normalizeTicker(ticker));
}

function parseKrNumber(raw: unknown): number | null {
  if (raw == null) return null;
  if (typeof raw === "number") return raw;
  const s = String(raw).replace(/,/g, "").replace(/\s/g, "").trim();
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

async function naverPrice(ticker: string) {
  const code = normalizeTicker(ticker);
  if (!/^\d{6}$/.test(code)) throw new Error(`Not a Korean ticker: ${ticker}`);
  const res = await fetch(
    `https://m.stock.naver.com/api/stock/${encodeURIComponent(code)}/basic`,
    { headers: UA },
  );
  if (!res.ok) throw new Error(`Naver ${code} HTTP ${res.status}`);
  const data = await res.json();
  const over = data?.overMarketPriceInfo ?? {};
  let price =
    over.overMarketStatus === "OPEN" ? parseKrNumber(over.overPrice) : null;
  if (price == null) {
    price = parseKrNumber(
      data?.closePrice ?? data?.dealPrice ?? data?.tradePrice,
    );
  }
  if (price == null) throw new Error(`Naver ${code} no price`);
  const name = String(data?.stockName || "").trim() || null;
  return {
    ticker: code,
    price,
    currency: "KRW",
    updated_at: new Date().toISOString(),
    name,
  };
}

async function yahooPrice(ticker: string) {
  const symbol = normalizeTicker(ticker);
  const url =
    `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1d&range=1d`;
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
  const name = String(meta.longName || meta.shortName || "").trim() || null;
  return {
    ticker: symbol,
    price: Number(price),
    currency: meta.currency ?? "USD",
    updated_at: new Date().toISOString(),
    name,
  };
}

async function fetchPrice(ticker: string) {
  const symbol = normalizeTicker(ticker);
  if (isKoreanTicker(symbol)) return await naverPrice(symbol);
  return await yahooPrice(symbol);
}

async function usdKrw() {
  const res = await fetch(
    "https://api.frankfurter.dev/v1/latest?from=USD&to=KRW",
  );
  if (!res.ok) throw new Error(`FX HTTP ${res.status}`);
  const data = await res.json();
  const rate = data?.rates?.KRW;
  if (rate == null) throw new Error("FX missing KRW");
  return Number(rate);
}

async function yahooIndex(symbol: string): Promise<number> {
  const url =
    `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1d&range=5d`;
  const res = await fetch(url, { headers: UA });
  if (!res.ok) throw new Error(`Yahoo index ${symbol} HTTP ${res.status}`);
  const payload = await res.json();
  const result = payload?.chart?.result?.[0];
  if (!result) throw new Error(`Yahoo index ${symbol} empty`);
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
  if (price == null) throw new Error(`Yahoo index ${symbol} no price`);
  return Number(price);
}

async function fetchIndices(): Promise<{ values: Record<string, number>; errors: string[] }> {
  const map: Record<string, string> = {
    sp500: "^GSPC",
    nasdaq: "^IXIC",
    kospi: "^KS11",
  };
  const values: Record<string, number> = {};
  const errors: string[] = [];
  for (const [col, sym] of Object.entries(map)) {
    try {
      values[col] = await yahooIndex(sym);
    } catch (e) {
      errors.push(`${col}(${sym}): ${e}`);
    }
  }
  return { values, errors };
}

Deno.serve(async (_req) => {
  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );
    const { data: holdings, error } = await supabase
      .from("holdings")
      .select("ticker");
    if (error) throw error;
    const tickers = [...new Set((holdings ?? []).map((h) => h.ticker))];
    const rows = [];
    const errors = [];
    for (const t of tickers) {
      const symbol = normalizeTicker(t);
      if (!symbol || PRIVATE.has(symbol)) {
        errors.push(`${symbol || "?"}: skipped`);
        continue;
      }
      try {
        rows.push(await fetchPrice(symbol));
      } catch (e) {
        errors.push(`${symbol}: ${e}`);
      }
    }
    if (rows.length) {
      const priceRows = rows.map(({ ticker, price, currency, updated_at }) => ({
        ticker,
        price,
        currency,
        updated_at,
      }));
      const { error: upErr } = await supabase.from("market_prices").upsert(priceRows);
      if (upErr) throw upErr;

      // Backfill 종목명 onto holdings so UI shows full names, not 005930
      for (const row of rows) {
        const name = (row.name || "").trim();
        if (!name || name.toUpperCase() === row.ticker) continue;
        const { error: nameErr } = await supabase
          .from("holdings")
          .update({ name })
          .eq("ticker", row.ticker);
        if (nameErr) errors.push(`${row.ticker} name: ${nameErr.message}`);
      }
    }
    const fx = await usdKrw();
    await supabase.from("market_prices").upsert({
      ticker: "USDKRW",
      price: fx,
      currency: "KRW",
      updated_at: new Date().toISOString(),
    });
    const { values: indices, errors: idxErrors } = await fetchIndices();
    errors.push(...idxErrors);
    const today = new Date().toISOString().slice(0, 10);
    await supabase.from("market_index_snapshots").upsert({
      snapshot_date: today,
      usdkrw: fx,
      ...indices,
    });
    const { data: snapshot, error: snapErr } = await supabase.rpc(
      "compute_daily_snapshot",
    );
    if (snapErr) {
      return Response.json({
        ok: true,
        updated: rows.length,
        fx,
        indices,
        errors: [...errors, `snapshot: ${snapErr.message}`],
      });
    }
    return Response.json({
      ok: true,
      updated: rows.length,
      fx,
      indices,
      errors,
      snapshot,
    });
  } catch (e) {
    return Response.json({ ok: false, error: String(e) }, { status: 500 });
  }
});
