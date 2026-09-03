import { SignedAmount, SignedPct } from "@/components/SignedValue";
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
      {cells.map((c) => (
        <div
          key={c.label}
          className="rounded-2xl border border-line bg-surface px-3 py-3 shadow-soft"
        >
          <div className="text-[11px] font-semibold text-muted">{c.label}</div>
          <div className="mt-1">
            <SignedAmount amount={c.pnl} className="text-base" />
          </div>
          <SignedPct value={c.pct} className="text-xs" />
        </div>
      ))}
    </div>
  );
}
