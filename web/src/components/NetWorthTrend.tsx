import { fmtKrw } from "@/lib/money";
import type { DailySnap } from "@/lib/portfolio";

export function NetWorthTrend({ snaps }: { snaps: DailySnap[] }) {
  const points = snaps
    .filter((s) => s.net_assets != null && Number.isFinite(Number(s.net_assets)))
    .map((s) => ({
      date: String(s.snapshot_date).slice(0, 10),
      value: Number(s.net_assets),
    }));

  if (points.length < 2) {
    return (
      <section className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
        <h2 className="text-base font-extrabold tracking-tight">순자산 추이</h2>
        <p className="mt-2 text-sm text-muted">
          스냅샷이 쌓이면 추이가 표시됩니다.
        </p>
      </section>
    );
  }

  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const w = 320;
  const h = 96;
  const pad = 8;
  const coords = points.map((p, i) => {
    const x = pad + (i * (w - pad * 2)) / Math.max(points.length - 1, 1);
    const y = h - pad - ((p.value - min) / span) * (h - pad * 2);
    return `${x},${y}`;
  });
  const polyline = coords.join(" ");
  const first = points[0];
  const last = points[points.length - 1];
  const change = last.value - first.value;

  return (
    <section className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h2 className="text-base font-extrabold tracking-tight">순자산 추이</h2>
          <p className="mt-0.5 text-xs text-muted">
            {first.date} → {last.date}
          </p>
        </div>
        <div className="text-right text-sm font-extrabold tracking-tight">
          {fmtKrw(change, { signed: true })}
        </div>
      </div>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="mt-3 h-24 w-full overflow-visible"
        role="img"
        aria-label="순자산 추이 차트"
      >
        <polyline
          fill="none"
          stroke="var(--brand)"
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
          points={polyline}
        />
      </svg>
      <div className="mt-1 flex justify-between text-[11px] font-semibold text-muted">
        <span>{fmtKrw(min)}</span>
        <span>{fmtKrw(max)}</span>
      </div>
    </section>
  );
}
