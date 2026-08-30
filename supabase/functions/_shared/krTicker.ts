/** Correct Korean 6-digit tickers using Naver when OCR name ≠ quote name. */

const UA = { "User-Agent": "Bujattung/1.0" };

export function normName(raw: unknown): string {
  return String(raw || "")
    .replace(/\s+/g, "")
    .replace(/적격/g, "")
    .toLowerCase();
}

export function namesAgree(a: unknown, b: unknown): boolean {
  const x = normName(a);
  const y = normName(b);
  if (!x || !y) return false;
  return x === y || x.includes(y) || y.includes(x);
}

function isKrCode(t: string): boolean {
  return /^\d{6}$/.test(t);
}

async function naverBasic(code: string): Promise<{ name: string; price: number | null } | null> {
  try {
    const res = await fetch(
      `https://m.stock.naver.com/api/stock/${encodeURIComponent(code)}/basic`,
      { headers: UA },
    );
    if (!res.ok) return null;
    const data = await res.json();
    const name = String(data?.stockName || "").trim();
    const raw = String(data?.closePrice || data?.dealPrice || data?.tradePrice || "")
      .replace(/,/g, "")
      .trim();
    const price = Number(raw);
    return {
      name,
      price: Number.isFinite(price) ? price : null,
    };
  } catch {
    return null;
  }
}

async function naverSearchTicker(name: string): Promise<string | null> {
  try {
    const res = await fetch(
      "https://m.stock.naver.com/front-api/search/autoComplete?" +
        new URLSearchParams({ query: name, target: "stock" }),
      { headers: UA },
    );
    if (!res.ok) return null;
    const payload = await res.json();
    const items = (payload?.result?.items || []) as Array<{ code?: string; name?: string }>;
    if (!items.length) return null;
    const exact = items.find((it) => namesAgree(name, it.name));
    const hit = exact || items[0];
    const code = String(hit?.code || "").trim();
    return isKrCode(code) ? code : null;
  } catch {
    return null;
  }
}

export type OcrRow = Record<string, unknown>;

export async function correctOcrRow(row: OcrRow): Promise<OcrRow> {
  const name = String(row.name || "").trim();
  let ticker = String(row.ticker || "").trim();
  if (!name && !ticker) return row;

  if (ticker && isKrCode(ticker) && name) {
    const quote = await naverBasic(ticker);
    if (quote?.name && namesAgree(name, quote.name)) {
      if (row.last_price == null && quote.price != null) row.last_price = quote.price;
      return row;
    }
  }

  if (name) {
    const found = await naverSearchTicker(name);
    if (found && found !== ticker) {
      row.ticker = found;
      ticker = found;
    }
  }

  if (ticker && isKrCode(ticker) && row.last_price == null) {
    const quote = await naverBasic(ticker);
    if (quote?.price != null) row.last_price = quote.price;
    if (quote?.name && (!name || !namesAgree(name, quote.name))) {
      if (!name) row.name = quote.name;
    }
  }
  return row;
}

export async function correctOcrParsed(
  parsed: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  for (const key of ["holdings_snapshot", "trades", "dividends"]) {
    const arr = parsed[key];
    if (!Array.isArray(arr)) continue;
    parsed[key] = await Promise.all(arr.map((row) => correctOcrRow(row as OcrRow)));
  }
  return parsed;
}
