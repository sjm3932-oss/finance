/** Korean ticker / 종목명 helpers for ledger and PnL display. */

const HANGUL = /[\uac00-\ud7a3]/;

export function normalizeKrTicker(raw: unknown): string {
  let t = String(raw || "").trim().toUpperCase();
  if (!t) return t;
  if (t.endsWith(".KS") || t.endsWith(".KQ")) t = t.slice(0, -3);
  // KIS sometimes pads an A-prefix: 00000A458730 → 458730
  const aIdx = t.indexOf("A");
  if (
    aIdx >= 0 &&
    /^\d*$/.test(t.slice(0, aIdx)) &&
    /^\d+$/.test(t.slice(aIdx + 1))
  ) {
    t = t.slice(aIdx + 1);
  }
  if (/^\d+$/.test(t) && t.length <= 6) return t.padStart(6, "0");
  if (/^\d+$/.test(t) && t.length > 6) return t.slice(-6);
  return t;
}

export function tickerLookupKeys(raw: unknown): string[] {
  const orig = String(raw || "").trim();
  if (!orig) return [];
  const keys = new Set<string>();
  keys.add(orig);
  keys.add(orig.toUpperCase());
  const norm = normalizeKrTicker(orig);
  if (norm) keys.add(norm);
  if (norm !== orig) keys.add(orig.replace(/^0+/, "") || orig);
  return [...keys];
}

/** True when the string is a code, not a human 종목명. */
export function isTickerLike(raw: unknown): boolean {
  const s = String(raw || "").trim();
  if (!s) return true;
  if (HANGUL.test(s) || /\s/.test(s)) return false;
  const norm = normalizeKrTicker(s);
  if (/^\d{6}$/.test(norm)) return true;
  // KIS product / ELW-style codes: 0180V0, 00000A458730
  if (/^[0-9A-Z]{4,16}$/.test(s.toUpperCase()) && !/[AEIOU]{2}/.test(s.toUpperCase())) {
    return /[0-9]/.test(s);
  }
  return false;
}

export function buildNameIndex(
  rows: Array<{ ticker?: string | null; name?: string | null }>
): Map<string, string> {
  const map = new Map<string, string>();
  const put = (key: string, name: string) => {
    if (!key || !name) return;
    const existing = map.get(key);
    if (existing && !isTickerLike(existing)) return;
    map.set(key, name);
  };
  for (const row of rows) {
    const name = String(row.name || "").trim();
    if (!name || isTickerLike(name)) continue;
    for (const key of tickerLookupKeys(row.ticker)) put(key, name);
  }
  return map;
}

export function lookupAssetName(
  ticker: unknown,
  names: Map<string, string>
): string | null {
  for (const key of tickerLookupKeys(ticker)) {
    const found = names.get(key);
    if (found) return found;
  }
  return null;
}

export function flowDisplayName(
  flow: {
    flow_kind?: string | null;
    asset_ref?: string | null;
    asset_name?: string | null;
  },
  kindKo: Record<string, string> = {}
): string {
  const named = String(flow.asset_name || "").trim();
  if (named) return named;
  const ref = String(flow.asset_ref || "").trim();
  if (ref) return ref;
  const kind = String(flow.flow_kind || "");
  return kindKo[kind] || kind || "항목";
}
