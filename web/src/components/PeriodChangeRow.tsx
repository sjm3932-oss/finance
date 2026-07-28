import { fmtKrw, fmtPct, retTone } from "@/lib/money";
import type { PeriodChange } from "@/lib/insights";

export function PeriodChangeRow({ period }: { period: PeriodChange }) {
  const cells = [
    {
      label: "오늘 손익",
      pnl: period.today_pnl,
      pct: period.today_pct,
    },
    {
      label: "이번 주 손익",
      pnl: period.week_pnl,
      pct: period.week_pct,
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-2">
      {cells.map((c) => {
        const tone = retTone(c.pct ?? c.pnl);
        return (
          <div
            key={c.label}
            className="rounded-2xl border border-line bg-surface px-3 py-3 shadow-soft"
          >
            <div className="text-[11px] font-semibold text-muted">{c.label}</div>
            <div
              className={`mt-1 text-base font-extrabold tracking-tight ${
                tone === "up"
                  ? "text-up"
                  : tone === "down"
                    ? "text-down"
                    : "text-ink"
              }`}
            >
              {fmtKrw(c.pnl, { signed: true })}
            </div>
            <div className="text-xs font-bold text-muted">{fmtPct(c.pct)}</div>
          </div>
        );
      })}
    </div>
  );
}
