import { fmtKrw, fmtPct, retTone } from "@/lib/money";
import type { MonthlySummary } from "@/lib/portfolio";

export function MonthlySummaryCard({ monthly }: { monthly: MonthlySummary }) {
  const tone = retTone(monthly.nw_change_pct);
  const toneClass =
    tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-ink";

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
          <div className={`mt-0.5 text-base font-extrabold tracking-tight ${toneClass}`}>
            {fmtKrw(monthly.nw_change, { signed: true })}
            <span className="ml-1 text-xs font-bold">
              {fmtPct(monthly.nw_change_pct)}
            </span>
          </div>
        </div>
        <div className="col-span-2">
          <div className="text-[11px] font-semibold text-muted">이달 실현손익</div>
          <div
            className={`mt-0.5 text-base font-extrabold tracking-tight ${
              retTone(monthly.realized_month) === "up"
                ? "text-up"
                : retTone(monthly.realized_month) === "down"
                  ? "text-down"
                  : "text-ink"
            }`}
          >
            {fmtKrw(monthly.realized_month, { signed: true })}
          </div>
        </div>
      </div>
    </section>
  );
}
