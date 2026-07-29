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
