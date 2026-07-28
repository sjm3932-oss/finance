import { fmtKrw } from "@/lib/money";

export function SimpleBarChart({
  title,
  subtitle,
  bars,
  signed = false,
}: {
  title: string;
  subtitle?: string;
  bars: { label: string; value: number; color?: string }[];
  signed?: boolean;
}) {
  if (!bars.length) {
    return (
      <section className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
        <h2 className="text-base font-extrabold tracking-tight">{title}</h2>
        <p className="mt-2 text-sm text-muted">표시할 데이터가 없습니다.</p>
      </section>
    );
  }

  const max = Math.max(...bars.map((b) => Math.abs(b.value)), 1);

  return (
    <section className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
      <h2 className="text-base font-extrabold tracking-tight">{title}</h2>
      {subtitle ? <p className="mt-0.5 text-xs text-muted">{subtitle}</p> : null}
      <div className="mt-3 space-y-2">
        {bars.map((b) => {
          const pct = (Math.abs(b.value) / max) * 100;
          const positive = b.value >= 0;
          const color =
            b.color || (positive ? "var(--up)" : "var(--down)");
          return (
            <div key={b.label}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="font-bold text-muted">{b.label}</span>
                <span className="font-extrabold tracking-tight">
                  {signed ? fmtKrw(b.value, { signed: true }) : fmtKrw(b.value)}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-canvas">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${pct}%`, background: color }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function DualLineChart({
  title,
  subtitle,
  a,
  b,
  aLabel,
  bLabel,
}: {
  title: string;
  subtitle?: string;
  a: { date: string; value: number }[];
  b: { date: string; value: number }[];
  aLabel: string;
  bLabel: string;
}) {
  const w = 320;
  const h = 120;
  const pad = 10;
  const all = [...a, ...b].map((p) => p.value);
  if (!a.length) {
    return (
      <section className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
        <h2 className="text-base font-extrabold tracking-tight">{title}</h2>
        <p className="mt-2 text-sm text-muted">비교할 데이터가 없습니다.</p>
      </section>
    );
  }
  const min = Math.min(...all, 95);
  const max = Math.max(...all, 105);
  const span = Math.max(max - min, 1);

  function poly(points: { date: string; value: number }[]) {
    return points
      .map((p, i) => {
        const x =
          pad + (i * (w - pad * 2)) / Math.max(points.length - 1, 1);
        const y = h - pad - ((p.value - min) / span) * (h - pad * 2);
        return `${x},${y}`;
      })
      .join(" ");
  }

  return (
    <section className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
      <h2 className="text-base font-extrabold tracking-tight">{title}</h2>
      {subtitle ? <p className="mt-0.5 text-xs text-muted">{subtitle}</p> : null}
      <svg viewBox={`0 0 ${w} ${h}`} className="mt-3 h-28 w-full">
        <polyline
          fill="none"
          stroke="var(--brand)"
          strokeWidth="2.5"
          points={poly(a)}
        />
        {b.length ? (
          <polyline
            fill="none"
            stroke="#9CA3AF"
            strokeWidth="2"
            strokeDasharray="4 3"
            points={poly(b)}
          />
        ) : null}
      </svg>
      <div className="mt-1 flex gap-3 text-[11px] font-semibold text-muted">
        <span className="text-brand">{aLabel}</span>
        {b.length ? <span>{bLabel}</span> : null}
      </div>
    </section>
  );
}
