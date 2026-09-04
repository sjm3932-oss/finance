import Link from "next/link";
import { fmtCompactKrw, fmtKrw } from "@/lib/money";
import { FlowAmount, SignedAmount } from "@/components/SignedValue";

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
        {bars.map((b, i) => {
          const pct = (Math.abs(b.value) / max) * 100;
          const positive = b.value >= 0;
          const color =
            b.color || (positive ? "var(--up)" : "var(--down)");
          return (
            <div key={`${b.label}-${i}`}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="font-bold text-muted">{b.label}</span>
                {signed ? (
                  <SignedAmount amount={b.value} className="text-xs" />
                ) : (
                  <span className="font-extrabold tracking-tight">
                    {fmtKrw(b.value)}
                  </span>
                )}
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

export function MonthlyFlowChart({
  title,
  months,
}: {
  title: string;
  months: { id?: string; label: string; inflow: number; outflow: number }[];
}) {
  if (!months.length) {
    return (
      <section className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
        <h2 className="text-base font-extrabold tracking-tight">{title}</h2>
        <p className="mt-2 text-sm text-muted">표시할 데이터가 없습니다.</p>
      </section>
    );
  }

  const max = Math.max(...months.map((m) => m.inflow + m.outflow), 1);

  return (
    <section className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-base font-extrabold tracking-tight">{title}</h2>
        <div className="flex shrink-0 items-center gap-2 text-[11px] font-bold">
          <span className="inline-flex items-center gap-1 text-up">
            <span className="h-2 w-2 rounded-full bg-up" />
            유입
          </span>
          <span className="inline-flex items-center gap-1 text-down">
            <span className="h-2 w-2 rounded-full bg-down" />
            유출
          </span>
        </div>
      </div>
      <div className="mt-3 space-y-3">
        {months.map((m) => {
          const total = m.inflow + m.outflow;
          const inPct = total ? (m.inflow / max) * 100 : 0;
          const outPct = total ? (m.outflow / max) * 100 : 0;
          const net = m.inflow - m.outflow;
          return (
            <div key={m.id || m.label}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="font-bold text-muted">{m.label}</span>
                <FlowAmount amount={net} signedNet className="text-xs" />
              </div>
              <div
                className="flex h-2.5 overflow-hidden rounded-full bg-canvas"
                role="img"
                aria-label={`${m.label} 유입 ${fmtKrw(m.inflow)}, 유출 ${fmtKrw(m.outflow)}`}
              >
                <div
                  className="h-full bg-up"
                  style={{ width: `${inPct}%` }}
                />
                <div
                  className="h-full bg-down"
                  style={{ width: `${outPct}%` }}
                />
              </div>
              <div className="mt-1 flex items-center justify-between text-[10px] font-bold">
                <span className="text-up">↑ {fmtKrw(m.inflow)}</span>
                <span className="text-down">↓ {fmtKrw(m.outflow)}</span>
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

export function TimeSeriesBarChart({
  title,
  subtitle,
  bars,
  windows,
  signed = true,
}: {
  title: string;
  subtitle?: string;
  bars: { key: string; label: string; value: number }[];
  windows?: { id: string; label: string; href: string; active: boolean }[];
  signed?: boolean;
}) {
  if (!bars.length) {
    return (
      <section className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
        <h2 className="text-base font-extrabold tracking-tight">{title}</h2>
        {windows?.length ? <YearWindowChips windows={windows} /> : null}
        <p className="mt-2 text-sm text-muted">표시할 데이터가 없습니다.</p>
      </section>
    );
  }

  const W = 360;
  const H = 160;
  const padL = 6;
  const padR = 6;
  const padT = 8;
  const padB = 28;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const max = Math.max(0, ...bars.map((b) => b.value), 1);
  const min = Math.min(0, ...bars.map((b) => b.value));
  const span = Math.max(max - min, 1);
  const yOf = (v: number) => padT + ((max - v) / span) * innerH;
  const zeroY = yOf(0);
  const slot = innerW / bars.length;
  const barW = Math.min(16, Math.max(6, slot * 0.58));
  const total = bars.reduce((s, b) => s + b.value, 0);

  return (
    <section className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-base font-extrabold tracking-tight">{title}</h2>
          {subtitle ? <p className="mt-0.5 text-xs text-muted">{subtitle}</p> : null}
        </div>
        {signed ? (
          <SignedAmount amount={total} className="shrink-0 text-sm" />
        ) : (
          <span className="shrink-0 text-sm font-extrabold tracking-tight">
            {fmtKrw(total)}
          </span>
        )}
      </div>
      {windows?.length ? <YearWindowChips windows={windows} /> : null}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="mt-3 h-40 w-full"
        role="img"
        aria-label={`${title}. ${bars
          .map((b) => `${b.label} ${fmtKrw(b.value, { signed: true })}`)
          .join(", ")}`}
      >
        <line
          x1={padL}
          x2={W - padR}
          y1={zeroY}
          y2={zeroY}
          stroke="var(--line)"
          strokeWidth="1"
        />
        {bars.map((b, i) => {
          const y1 = yOf(b.value);
          const x = padL + slot * i + (slot - barW) / 2;
          const top = Math.min(y1, zeroY);
          const height = b.value === 0 ? 0 : Math.max(Math.abs(y1 - zeroY), 2);
          const color =
            b.value > 0 ? "var(--up)" : b.value < 0 ? "var(--down)" : "#D1D5DB";
          const labelY = H - 10;
          return (
            <g key={b.key}>
              {height ? (
                <rect
                  x={x}
                  y={top}
                  width={barW}
                  height={height}
                  rx="2"
                  fill={color}
                />
              ) : null}
              <text
                x={padL + slot * i + slot / 2}
                y={labelY}
                textAnchor="middle"
                fontSize="8.5"
                fontWeight="700"
                fill="#6B7280"
              >
                {b.label}
              </text>
            </g>
          );
        })}
      </svg>
      <ul className="mt-2 grid grid-cols-3 gap-x-3 gap-y-1 sm:grid-cols-4">
        {bars.map((b) => {
          const tone =
            b.value > 0 ? "text-up" : b.value < 0 ? "text-down" : "text-muted";
          return (
            <li
              key={b.key}
              className="flex items-baseline justify-between gap-1 text-[11px]"
            >
              <span className="font-bold text-muted">{b.label}</span>
              <span className={`font-extrabold tabular-nums ${tone}`}>
                {b.value === 0
                  ? "—"
                  : `${b.value > 0 ? "↑" : "↓"} ${fmtCompactKrw(b.value)}`}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function YearWindowChips({
  windows,
}: {
  windows: { id: string; label: string; href: string; active: boolean }[];
}) {
  return (
    <div className="mt-3 flex flex-wrap gap-1.5" role="group" aria-label="기간">
      {windows.map((w) => (
        <Link
          key={w.id}
          href={w.href}
          aria-current={w.active ? "page" : undefined}
          className={`inline-flex min-h-9 items-center rounded-lg px-2.5 py-1.5 text-[11px] font-bold ${
            w.active
              ? "bg-brand text-white"
              : "bg-canvas text-muted ring-1 ring-line"
          }`}
        >
          {w.label}
        </Link>
      ))}
    </div>
  );
}
