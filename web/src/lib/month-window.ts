/** Realized P&L / dividend period windows. Monthly charts stay at most 12 months. */

export const LAST_12M = "12m";
export type PeriodId = "1m" | "3m" | "6m" | "12m" | "ytd" | string;
/** @deprecated use PeriodId */
export type YearWindow = PeriodId;

const YEAR_RE = /^\d{4}$/;
const ROLLING: Record<string, number> = { "1m": 1, "3m": 3, "6m": 6, "12m": 12 };

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

export function parsePeriodWindow(
  raw: string | undefined | null,
  years: string[],
  nowYm?: string
): PeriodId {
  const v = String(raw || "").trim();
  if (!v || v === LAST_12M) return LAST_12M;
  if (v === "1m" || v === "3m" || v === "6m" || v === "ytd") return v;
  if (isCalendarYear(v) && years.includes(v)) return v;
  if (isCalendarYear(v) && nowYm && v === nowYm.slice(0, 4)) return "ytd";
  return LAST_12M;
}

/** @deprecated use parsePeriodWindow */
export function parseYearWindow(
  raw: string | undefined | null,
  years: string[]
): PeriodId {
  return parsePeriodWindow(raw, years);
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

export function monthKeysForPeriod(period: PeriodId, nowYm: string): string[] {
  if (period === "ytd") return monthKeysForYear(String(nowYm).slice(0, 4), nowYm);
  const rolling = ROLLING[period];
  if (rolling) return lastNMonthKeys(nowYm, rolling);
  return monthKeysForYear(period, nowYm);
}

/** @deprecated use monthKeysForPeriod */
export function monthKeysForWindow(window: PeriodId, nowYm: string): string[] {
  return monthKeysForPeriod(window, nowYm);
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

export function monthInPeriod(date: string, monthKeys: string[]): boolean {
  const month = String(date || "").slice(0, 7);
  return monthKeys.includes(month);
}

export function formatMonthTick(month: string, includeYear: boolean): string {
  const mm = String(month || "").slice(5, 7);
  const n = Number(mm);
  if (includeYear) {
    const yy = String(month || "").slice(2, 4);
    return `${yy}.${mm}`;
  }
  return Number.isFinite(n) && n > 0 ? `${n}월` : mm;
}

export function periodLabel(period: PeriodId, nowYm: string): string {
  if (period === "1m") return "이번 달";
  if (period === "3m") return "최근 3개월";
  if (period === "6m") return "최근 6개월";
  if (period === "12m") return "최근 12개월";
  if (period === "ytd") return `${String(nowYm).slice(0, 4)}년`;
  if (isCalendarYear(period)) return `${period}년`;
  return "최근 12개월";
}

/** @deprecated use periodLabel */
export function yearWindowLabel(window: PeriodId, nowYm = ""): string {
  return periodLabel(window, nowYm);
}

export function periodOptions(
  years: string[],
  nowYm: string
): Array<{ id: PeriodId; label: string }> {
  const currentYear = String(nowYm).slice(0, 4);
  const pastYears = years.filter((y) => y !== currentYear);
  return [
    { id: "1m", label: "이번 달" },
    { id: "3m", label: "3개월" },
    { id: "6m", label: "6개월" },
    { id: "12m", label: "12개월" },
    { id: "ytd", label: "올해" },
    ...pastYears.map((y) => ({ id: y, label: `${y}년` })),
  ];
}

/** @deprecated use periodOptions */
export function yearWindowOptions(
  years: string[],
  nowYm = ""
): Array<{ id: PeriodId; label: string }> {
  return periodOptions(years, nowYm);
}
