export function fmtKrw(
  v: number | null | undefined,
  opts?: { signed?: boolean }
): string {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
  const n = Number(v);
  const body = `₩${Math.abs(n).toLocaleString("ko-KR", {
    maximumFractionDigits: 0,
  })}`;
  if (opts?.signed) {
    if (n > 0) return `+${body}`;
    if (n < 0) return `-${body}`;
    return body;
  }
  return n < 0 ? `-${body}` : body;
}

export function fmtMoney(
  v: number | null | undefined,
  currency?: string | null,
  opts?: { signed?: boolean }
): string {
  const ccy = String(currency || "KRW").toUpperCase();
  if (ccy === "USD") {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
    const n = Number(v);
    const body = `$${Math.abs(n).toLocaleString("en-US", {
      maximumFractionDigits: 2,
    })}`;
    if (opts?.signed) {
      if (n > 0) return `+${body}`;
      if (n < 0) return `-${body}`;
      return body;
    }
    return n < 0 ? `-${body}` : body;
  }
  return fmtKrw(v, opts);
}

/** 체결 대금: 수량 × 단가 (±수수료). 매수는 실현손익이 없어서 이걸 보여준다. */
export function tradeNotional(t: {
  price?: unknown;
  quantity?: unknown;
  fee?: unknown;
  trade_type?: unknown;
}): number {
  const qty = Number(t.quantity || 0);
  const price = Number(t.price || 0);
  const fee = Number(t.fee || 0);
  const gross = qty * price;
  if (!Number.isFinite(gross)) return 0;
  return String(t.trade_type) === "sell" ? gross - fee : gross + fee;
}

/** 평단·체결단가: 천 단위 쉼표, KRW는 정수만. */
export function fmtUnitPrice(
  v: number | string | null | undefined,
  currency?: string | null
): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  const ccy = String(currency || "KRW").toUpperCase();
  if (ccy === "USD") {
    return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
  }
  return Math.round(n).toLocaleString("ko-KR");
}

export function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
  const n = Number(v);
  const sign = n > 0.005 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

/** Korean market convention: + red/up, − blue/down. */
export function signedTone(
  v: number | null | undefined,
  opts?: { epsilon?: number }
): "up" | "down" | "flat" {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "flat";
  const n = Number(v);
  const eps = opts?.epsilon ?? 0;
  if (n > eps) return "up";
  if (n < -eps) return "down";
  return "flat";
}

export function signedArrow(tone: "up" | "down" | "flat"): "↑" | "↓" | "" {
  if (tone === "up") return "↑";
  if (tone === "down") return "↓";
  return "";
}

/** Percentage with ↑/↓, for SVG / plain text (no color class). */
export function fmtPctArrow(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
  const n = Number(v);
  const arrow = signedArrow(signedTone(n, { epsilon: 0.005 }));
  const body = `${Math.abs(n).toFixed(2)}%`;
  return arrow ? `${arrow} ${body}` : body;
}

export function retTone(v: number | null | undefined): "up" | "down" | "flat" {
  return signedTone(v, { epsilon: 0.05 });
}

export function marketRegion(ticker: string | null | undefined, ccy?: string | null) {
  const t = String(ticker || "").trim();
  if (/^\d{6}$/.test(t)) return "국내";
  if ((ccy || "").toUpperCase() === "KRW") return "국내";
  return "해외";
}
