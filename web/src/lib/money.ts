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

export function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
  const n = Number(v);
  const sign = n > 0.005 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

export function retTone(v: number | null | undefined): "up" | "down" | "flat" {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "flat";
  if (v > 0.05) return "up";
  if (v < -0.05) return "down";
  return "flat";
}

export function marketRegion(ticker: string | null | undefined, ccy?: string | null) {
  const t = String(ticker || "").trim();
  if (/^\d{6}$/.test(t)) return "국내";
  if ((ccy || "").toUpperCase() === "KRW") return "국내";
  return "해외";
}
