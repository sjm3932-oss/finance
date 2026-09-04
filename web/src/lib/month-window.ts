/** Calendar-month windows for PnL / dividend time-series charts. Max 12 months. */

export const LAST_12M = "12m";
export type YearWindow = typeof LAST_12M | string;

const YEAR_RE = /^\d{4}$/;

export function isCalendarYear(raw: string): boolean {
  return YEAR_RE.test(raw);
}

export function yearsFromMonthKeys(months: Iterable<string>): string[] {
  const years = new Set<string>();
  for (const month of months) {
    const y = String(month || "").slice(0, 4);
    if (YEAR_RE.test(y)) years.add(y);
  }
  return [...years].sort();
}

export function parseYearWindow(
  raw: string | undefined | null,
  years: string[]
): YearWindow {
  const v = String(raw || "").trim();
  if (!v || v === LAST_12M) return LAST_12M;
  if (isCalendarYear(v) && years.includes(v)) return v;
  return LAST_12M;
}

/** Inclusive YYYY-MM keys, oldest first. `count` is capped at 12. */
export function lastNMonthKeys(nowYm: string, count = 12): string[] {
  const n = Math.min(12, Math.max(1, count));
  const [ys, ms] = String(nowYm).split("-");
  const y = Number(ys);
  const m = Number(ms);
  if (!y || !m) return [];
  const out: string[] = [];
  for (let i = n - 1; i >= 0; i--) {
    const dt = new Date(Date.UTC(y, m - 1 - i, 1));
    out.push(
      `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, "0")}`
    );
  }
  return out;
}

/** Calendar year months, not past the current month when `year` is this year. */
export function monthKeysForYear(year: string, nowYm: string): string[] {
  if (!isCalendarYear(year)) return [];
  const y = Number(year);
  const [ny, nm] = String(nowYm).split("-").map(Number);
  const last = ny === y ? Math.min(12, Math.max(1, nm || 12)) : 12;
  const out: string[] = [];
  for (let m = 1; m <= last; m++) {
    out.push(`${year}-${String(m).padStart(2, "0")}`);
  }
  return out;
}

export function monthKeysForWindow(window: YearWindow, nowYm: string): string[] {
  if (window === LAST_12M) return lastNMonthKeys(nowYm, 12);
  return monthKeysForYear(window, nowYm);
}

export function fillMonthSeries(
  rows: Array<{ month: string; value: number }>,
  keys: string[]
): Array<{ month: string; value: number }> {
  const map = new Map<string, number>();
  for (const row of rows) {
    const month = String(row.month || "").slice(0, 7);
    if (!month) continue;
    map.set(month, (map.get(month) || 0) + Number(row.value || 0));
  }
  return keys.map((month) => ({ month, value: map.get(month) || 0 }));
}

export function formatMonthTick(month: string, window: YearWindow): string {
  const mm = String(month || "").slice(5, 7);
  const n = Number(mm);
  if (window === LAST_12M) {
    const yy = String(month || "").slice(2, 4);
    return `${yy}.${mm}`;
  }
  return Number.isFinite(n) && n > 0 ? `${n}월` : mm;
}

export function yearWindowLabel(window: YearWindow): string {
  if (window === LAST_12M) return "최근 12개월";
  return `${window}년`;
}

export function yearWindowOptions(years: string[]): Array<{
  id: YearWindow;
  label: string;
}> {
  return [
    { id: LAST_12M, label: "최근 12개월" },
    ...years.map((y) => ({ id: y, label: `${y}년` })),
  ];
}
