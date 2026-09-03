"use client";

import { useMemo, useState } from "react";
import { daysAgoKst } from "@/lib/dates";
import { fmtKrw } from "@/lib/money";
import type { DailySnap } from "@/lib/portfolio";
import { DualLineChart } from "@/components/Charts";
import { SignedAmount } from "@/components/SignedValue";

export function NetWorthTrend({
  snaps,
  benchmark,
  title = "순자산 추이",
}: {
  snaps: DailySnap[];
  benchmark?: {
    portfolio: { date: string; value: number }[];
    index: { date: string; value: number }[];
    indexKey: string;
  } | null;
  title?: string;
}) {
  const [months, setMonths] = useState<number | null>(12);

  const points = useMemo(() => {
    let list = snaps
      .filter((s) => s.net_assets != null && Number.isFinite(Number(s.net_assets)))
      .map((s) => ({
        date: String(s.snapshot_date).slice(0, 10),
        value: Number(s.net_assets),
      }));
    if (months) {
      const iso = daysAgoKst(Math.round(months * 30.4));
      list = list.filter((p) => p.date >= iso);
    }
    return list;
  }, [snaps, months]);

  if (points.length < 2) {
    return (
      <section className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
        <h2 className="text-base font-extrabold tracking-tight">{title}</h2>
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
  const first = points[0];
  const last = points[points.length - 1];
  const change = last.value - first.value;

  const indexLabel =
    benchmark?.indexKey === "nasdaq"
      ? "NASDAQ"
      : benchmark?.indexKey === "kospi"
        ? "KOSPI"
        : "S&P 500";

  return (
    <div className="space-y-3">
      <section className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h2 className="text-base font-extrabold tracking-tight">{title}</h2>
            <p className="mt-0.5 text-xs text-muted">
              {first.date} → {last.date}
            </p>
          </div>
          <div className="text-right">
            <SignedAmount amount={change} className="text-sm" />
          </div>
        </div>
        <div className="mt-2 flex gap-1">
          {[3, 6, 12, 36].map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMonths(m)}
              className={`rounded-lg px-2 py-1 text-[11px] font-bold ${
                months === m ? "bg-brand text-white" : "bg-canvas text-muted"
              }`}
            >
              {m}M
            </button>
          ))}
          <button
            type="button"
            onClick={() => setMonths(null)}
            className={`rounded-lg px-2 py-1 text-[11px] font-bold ${
              months === null ? "bg-brand text-white" : "bg-canvas text-muted"
            }`}
          >
            전체
          </button>
        </div>
        <svg
          viewBox={`0 0 ${w} ${h}`}
          className="mt-3 h-24 w-full"
          role="img"
          aria-label="순자산 추이"
        >
          <polyline
            fill="none"
            stroke="var(--brand)"
            strokeWidth="2.5"
            strokeLinejoin="round"
            strokeLinecap="round"
            points={coords.join(" ")}
          />
        </svg>
        <div className="mt-1 flex justify-between text-[11px] font-semibold text-muted">
          <span>{fmtKrw(min)}</span>
          <span>{fmtKrw(max)}</span>
        </div>
      </section>

      {benchmark && benchmark.portfolio.length > 1 ? (
        <DualLineChart
          title="수익률 비교 (시작=100)"
          subtitle={`내 투자자산 vs ${indexLabel}`}
          a={benchmark.portfolio}
          b={benchmark.index}
          aLabel="내 포트폴리오"
          bLabel={indexLabel}
        />
      ) : null}
    </div>
  );
}
