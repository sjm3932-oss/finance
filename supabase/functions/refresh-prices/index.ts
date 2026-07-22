// Supabase Edge Function: refresh Yahoo prices + USD/KRW into market_prices
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const PRIVATE = new Set(["SPACEX", "PRIVATE"]);

async function yahooPrice(ticker: string) {
  const url =
    `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?interval=1d&range=1d`;
  const res = await fetch(url, {
    headers: { "User-Agent": "CouplesWealthMaster/1.0" },
  });
  if (!res.ok) throw new Error(`Yahoo ${ticker} HTTP ${res.status}`);
  const payload = await res.json();
  const result = payload?.chart?.result?.[0];
  if (!result) throw new Error(`Yahoo ${ticker} empty`);
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
  if (price == null) throw new Error(`Yahoo ${ticker} no price`);
  return {
    ticker,
    price: Number(price),
    currency: meta.currency ?? "USD",
    updated_at: new Date().toISOString(),
  };
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
      const symbol = String(t || "").toUpperCase();
      if (!symbol || PRIVATE.has(symbol)) {
        errors.push(`${symbol || "?"}: skipped`);
        continue;
      }
      try {
        rows.push(await yahooPrice(symbol));
      } catch (e) {
        errors.push(`${symbol}: ${e}`);
      }
    }
    if (rows.length) {
      const { error: upErr } = await supabase.from("market_prices").upsert(rows);
      if (upErr) throw upErr;
    }
    const fx = await usdKrw();
    await supabase.from("market_prices").upsert({
      ticker: "USDKRW",
      price: fx,
      currency: "KRW",
      updated_at: new Date().toISOString(),
    });
    const today = new Date().toISOString().slice(0, 10);
    await supabase.from("market_index_snapshots").upsert({
      snapshot_date: today,
      usdkrw: fx,
    });
    const { data: snapshot, error: snapErr } = await supabase.rpc(
      "compute_daily_snapshot",
    );
    if (snapErr) {
      return Response.json({
        ok: true,
        updated: rows.length,
        fx,
        errors: [...errors, `snapshot: ${snapErr.message}`],
      });
    }
    return Response.json({ ok: true, updated: rows.length, fx, errors, snapshot });
  } catch (e) {
    return Response.json({ ok: false, error: String(e) }, { status: 500 });
  }
});
