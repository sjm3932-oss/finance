import { SignedAmount, SignedPct } from "@/components/SignedValue";
import { fmtKrw } from "@/lib/money";
import type { MonthlySummary } from "@/lib/portfolio";

export function MonthlySummaryCard({ monthly }: { monthly: MonthlySummary }) {
  return (
    <section className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
      <h2 className="text-base font-extrabold tracking-tight">이번 달 요약</h2>
      <p className="mt-0.5 text-xs text-muted">
        월초 스냅샷 대비 · {monthly.month_start}
      </p>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <div>
          <div className="text-[11px] font-semibold text-muted">순자산</div>
          <div className="mt-0.5 text-base font-extrabold tracking-tight">
            {fmtKrw(monthly.nw_now)}
          </div>
        </div>
        <div>
          <div className="text-[11px] font-semibold text-muted">월초 대비</div>
          <div className="mt-0.5 flex flex-wrap items-baseline gap-1">
            <SignedAmount amount={monthly.nw_change} className="text-base" />
            <SignedPct value={monthly.nw_change_pct} className="text-xs" />
          </div>
        </div>
        <div className="col-span-2">
          <div className="text-[11px] font-semibold text-muted">이달 실현손익</div>
          <div className="mt-0.5">
            <SignedAmount amount={monthly.realized_month} className="text-base" />
          </div>
        </div>
      </div>
    </section>
  );
}
