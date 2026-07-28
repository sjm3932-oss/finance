import type { LiveHolding } from "@/lib/portfolio";

export type PeriodChange = {
  today_pnl: number | null;
  today_pct: number | null;
  week_pnl: number | null;
  week_pct: number | null;
};

export type TreemapLeaf = {
  id: string;
  label: string;
  ticker: string;
  value: number;
  return_pct: number;
  path: string[];
};

export type HoldingSnapRow = {
  snapshot_date: string;
  account_id: string;
  ticker?: string;
  market_value_krw: number | null;
};

export type RealizedRow = {
  event_date: string;
  pnl_kind: string;
  pnl_kind_ko: string;
  asset_ref: string;
  asset_name: string;
  pnl: number;
  currency: string;
  pnl_krw: number;
  account_id: string | null;
  detail: string;
};

export type DividendRow = {
  id?: string;
  pay_date: string;
  ticker: string;
  name: string | null;
  amount: number;
  currency: string | null;
  account_id: string | null;
  memo: string | null;
};

export type FlowRow = {
  event_date: string;
  flow_kind: string;
  flow_subtype?: string | null;
  asset_ref?: string | null;
  amount: number;
  currency?: string | null;
  memo?: string | null;
  account_id?: string | null;
};

export type IndexSnap = {
  snapshot_date: string;
  nasdaq?: number | null;
  sp500?: number | null;
  kospi?: number | null;
};

export const PNL_KIND_KO: Record<string, string> = {
  trade_realized: "매매실현",
  dividend: "배당",
  interest_income: "이자수입",
  interest_expense: "이자비용",
};

export const FLOW_KIND_KO: Record<string, string> = {
  trade: "매매",
  dividend: "배당",
  cash_flow: "현금흐름",
  debt: "부채",
};

export const DEBT_KIND_KO: Record<string, string> = {
  mortgage: "주택담보",
  credit: "신용대출",
  card: "카드론",
  student: "학자금",
  jeonse: "전세자금",
  other: "기타",
};

function sumOnDate(
  snaps: HoldingSnapRow[],
  on: string,
  accountIds: string[] | null
): number | null {
  const part = snaps.filter((s) => {
    if (String(s.snapshot_date).slice(0, 10) !== on) return false;
    if (accountIds && !accountIds.includes(s.account_id)) return false;
    return true;
  });
  if (!part.length) return null;
  const vals = part.map((s) => Number(s.market_value_krw));
  if (!vals.some((v) => Number.isFinite(v))) return null;
  return vals.reduce((a, b) => a + (Number.isFinite(b) ? b : 0), 0);
}

function nearestPrior(dates: string[], before: string): string | null {
  const prior = dates.filter((d) => d < before);
  return prior.length ? prior[prior.length - 1] : null;
}

export function periodChangeStats(
  liveValueKrw: number | null,
  snaps: HoldingSnapRow[],
  accountIds: string[] | null,
  now = new Date()
): PeriodChange {
  const out: PeriodChange = {
    today_pnl: null,
    today_pct: null,
    week_pnl: null,
    week_pct: null,
  };
  if (liveValueKrw == null) return out;

  const today = now.toISOString().slice(0, 10);
  const dates = [
    ...new Set(snaps.map((s) => String(s.snapshot_date).slice(0, 10))),
  ].sort();

  const y = new Date(now);
  y.setDate(y.getDate() - 1);
  const yIso = y.toISOString().slice(0, 10);
  const w = new Date(now);
  w.setDate(w.getDate() - 7);
  const wIso = w.toISOString().slice(0, 10);

  const ref1 =
    sumOnDate(snaps, yIso, accountIds) ??
    sumOnDate(snaps, nearestPrior(dates, today) || "", accountIds);
  const ref7 =
    sumOnDate(snaps, wIso, accountIds) ??
    sumOnDate(snaps, nearestPrior(dates, wIso) || "", accountIds);

  if (ref1 != null && Math.abs(ref1) > 1) {
    out.today_pnl = liveValueKrw - ref1;
    out.today_pct = (100 * out.today_pnl) / ref1;
  }
  if (ref7 != null && Math.abs(ref7) > 1) {
    out.week_pnl = liveValueKrw - ref7;
    out.week_pct = (100 * out.week_pnl) / ref7;
  }
  return out;
}

export function buildTreemapLeaves(
  live: LiveHolding[],
  mode: "ticker" | "region" | "account" = "ticker"
): TreemapLeaf[] {
  const map = new Map<
    string,
    { label: string; ticker: string; value: number; retSum: number; n: number; path: string[] }
  >();

  for (const r of live) {
    const v = r.value_krw || 0;
    if (v <= 0) continue;
    const label = r.name || r.ticker;
    let key: string;
    let path: string[];
    if (mode === "region") {
      key = `${r.region}::${r.ticker}`;
      path = [r.region, label];
    } else if (mode === "account") {
      key = `${r.institution}::${r.ticker}`;
      path = [r.institution || "계좌", label];
    } else {
      key = r.ticker;
      path = [label];
    }
    const cur = map.get(key) || {
      label,
      ticker: r.ticker,
      value: 0,
      retSum: 0,
      n: 0,
      path,
    };
    cur.value += v;
    if (r.return_pct != null) {
      cur.retSum += r.return_pct;
      cur.n += 1;
    }
    map.set(key, cur);
  }

  return [...map.entries()]
    .map(([id, x]) => ({
      id,
      label: x.label,
      ticker: x.ticker,
      value: x.value,
      return_pct: x.n ? x.retSum / x.n : 0,
      path: x.path,
    }))
    .sort((a, b) => b.value - a.value);
}

/** Simple row-based treemap layout (not full squarify). */
export function layoutTreemap(
  leaves: TreemapLeaf[],
  width: number,
  height: number
): Array<TreemapLeaf & { x: number; y: number; w: number; h: number }> {
  const total = leaves.reduce((s, l) => s + l.value, 0);
  if (!total || !leaves.length) return [];

  const out: Array<TreemapLeaf & { x: number; y: number; w: number; h: number }> =
    [];
  let x = 0;
  let y = 0;
  let rowH = 0;
  let rowW = width;
  let remaining = total;
  let i = 0;

  while (i < leaves.length) {
    const leaf = leaves[i];
    const ratio = leaf.value / remaining;
    const useVertical = rowW >= height - y || leaves.length - i <= 2;
    if (useVertical) {
      const w = Math.max(24, ratio * rowW);
      const h = height - y;
      out.push({ ...leaf, x, y, w: Math.min(w, rowW), h });
      x += w;
      rowW -= w;
      remaining -= leaf.value;
      i++;
      if (rowW < 40 || i === leaves.length) {
        x = 0;
        y += h;
        rowW = width;
        if (y >= height - 8) break;
      }
    } else {
      const h = Math.max(28, ratio * (height - y));
      const w = rowW;
      out.push({ ...leaf, x, y, w, h });
      y += h;
      remaining -= leaf.value;
      i++;
    }
    rowH = y;
    if (rowH > height) break;
  }
  return out;
}

export function returnColor(pct: number): string {
  // red (down) ← 0 → green (up); Korea convention: up=red, down=blue in stock
  // Streamlit treemap used green up / red down for US-style; product uses up=#E11D48 down=#2563EB
  if (pct > 0.05) return "#E11D48";
  if (pct < -0.05) return "#2563EB";
  return "#9CA3AF";
}

export function toKrwAmount(
  amount: number,
  ccy: string | null | undefined,
  usdkrw: number | null
): number {
  if ((ccy || "KRW").toUpperCase() === "USD") {
    return usdkrw ? amount * usdkrw : 0;
  }
  return amount;
}

export function aggregateByMonth(
  rows: { date: string; value: number; key?: string }[]
): { month: string; value: number; key: string }[] {
  const map = new Map<string, number>();
  for (const r of rows) {
    const month = String(r.date).slice(0, 7);
    const k = `${month}::${r.key || "all"}`;
    map.set(k, (map.get(k) || 0) + r.value);
  }
  return [...map.entries()]
    .map(([k, value]) => {
      const [month, key] = k.split("::");
      return { month, key, value };
    })
    .sort((a, b) => a.month.localeCompare(b.month));
}

export function normalizeSeries(
  points: { date: string; value: number }[]
): { date: string; value: number }[] {
  if (!points.length) return [];
  const base = points[0].value;
  if (!base) return points.map((p) => ({ ...p, value: 100 }));
  return points.map((p) => ({
    date: p.date,
    value: (100 * p.value) / base,
  }));
}

export function dividendStats(
  rows: DividendRow[],
  usdkrw: number | null,
  now = new Date()
) {
  const y = now.getFullYear();
  const m = now.getMonth() + 1;
  const monthPrefix = `${y}-${String(m).padStart(2, "0")}`;
  let month = 0;
  let ytd = 0;
  const byMonth = new Map<string, number>();

  for (const r of rows) {
    const krw = toKrwAmount(Number(r.amount || 0), r.currency, usdkrw);
    const d = String(r.pay_date).slice(0, 10);
    const mo = d.slice(0, 7);
    byMonth.set(mo, (byMonth.get(mo) || 0) + krw);
    if (d.startsWith(monthPrefix)) month += krw;
    if (d.startsWith(String(y))) ytd += krw;
  }

  const months = [...byMonth.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .slice(-12);
  const avg =
    months.length > 0
      ? months.reduce((s, [, v]) => s + v, 0) / months.length
      : 0;

  return {
    month_krw: month,
    ytd_krw: ytd,
    avg_month_krw: avg,
    expected_krw: avg,
    monthly: months.map(([month, value]) => ({ month, value })),
  };
}
