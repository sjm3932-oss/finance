/** Asia/Seoul calendar dates (YYYY-MM-DD). Avoid UTC `toISOString().slice(0,10)`. */

export function formatKstDate(date: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

export function todayKst(): string {
  return formatKstDate(new Date());
}

export function monthStartKst(date: Date = new Date()): string {
  return `${formatKstDate(date).slice(0, 8)}01`;
}

/** Whole calendar days from `fromIso` to `toIso` (YYYY-MM-DD). */
export function calendarDaysBetween(fromIso: string, toIso: string): number {
  const [y1, m1, d1] = fromIso.split("-").map(Number);
  const [y2, m2, d2] = toIso.split("-").map(Number);
  const t1 = Date.UTC(y1, m1 - 1, d1);
  const t2 = Date.UTC(y2, m2 - 1, d2);
  return Math.round((t2 - t1) / 86_400_000);
}

/** Shift a calendar YYYY-MM-DD by `days` (date-only arithmetic). */
export function addCalendarDays(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + days));
  const yy = dt.getUTCFullYear();
  const mm = String(dt.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(dt.getUTCDate()).padStart(2, "0");
  return `${yy}-${mm}-${dd}`;
}

export function daysAgoKst(days: number, date: Date = new Date()): string {
  return addCalendarDays(formatKstDate(date), -days);
}

export function parseIsoDate(iso: string): [number, number, number] | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || "").trim());
  if (!m) return null;
  return [Number(m[1]), Number(m[2]), Number(m[3])];
}

/** Whole calendar months from `fromIso` to `toIso`, waiting until the start day-of-month. */
export function calendarMonthsBetween(fromIso: string, toIso: string): number {
  const a = parseIsoDate(fromIso);
  const b = parseIsoDate(toIso);
  if (!a || !b) return 0;
  let months = (b[0] - a[0]) * 12 + (b[1] - a[1]);
  if (b[2] < a[2]) months -= 1;
  return Math.max(0, months);
}
