import { fmtPct, retTone } from "@/lib/money";
import type { AllocationRow } from "@/lib/portfolio";

export function AllocationDriftTable({ rows }: { rows: AllocationRow[] }) {
  const warn = rows.some((r) => Math.abs(r.drift_pct) >= 5);

  return (
    <section className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
      <h2 className="text-base font-extrabold tracking-tight">자산 배분 · 목표 괴리</h2>
      <p className="mt-0.5 text-xs text-muted">총자산 대비 현재% / 목표%</p>
      {warn ? (
        <p className="mt-2 rounded-lg bg-brand-soft px-3 py-2 text-xs font-semibold text-brand-dark">
          일부 항목이 목표 대비 5%p 이상 벗어났습니다.
        </p>
      ) : null}
      <div className="mt-3 overflow-hidden rounded-xl ring-1 ring-line">
        <div className="grid grid-cols-4 bg-canvas px-3 py-2 text-[11px] font-bold text-muted">
          <span>구분</span>
          <span className="text-right">현재</span>
          <span className="text-right">목표</span>
          <span className="text-right">괴리</span>
        </div>
        {rows.map((r) => {
          const tone = retTone(r.drift_pct);
          return (
            <div
              key={r.category}
              className="grid grid-cols-4 border-t border-line px-3 py-2.5 text-sm"
            >
              <span className="font-bold tracking-tight">{r.label}</span>
              <span className="text-right font-semibold">
                {r.actual_pct.toFixed(1)}%
              </span>
              <span className="text-right text-muted">
                {r.target_pct.toFixed(1)}%
              </span>
              <span
                className={`text-right font-bold ${
                  tone === "up"
                    ? "text-up"
                    : tone === "down"
                      ? "text-down"
                      : "text-muted"
                }`}
              >
                {fmtPct(r.drift_pct).replace("%", "%p")}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
