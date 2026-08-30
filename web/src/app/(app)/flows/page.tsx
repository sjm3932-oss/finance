import { Suspense } from "react";
import { PortfolioFilters } from "@/components/PortfolioFilters";
import { SimpleBarChart } from "@/components/Charts";
import { loadPortfolioSnapshot } from "@/lib/data";
import { loadAssetFlows } from "@/lib/data-insights";
import { accountIdsForInstitution } from "@/lib/portfolio";
import { FLOW_KIND_KO, aggregateByMonth } from "@/lib/insights";
import { fmtKrw } from "@/lib/money";

export const dynamic = "force-dynamic";

export default async function FlowsPage({
  searchParams,
}: {
  searchParams: Promise<{ own?: string; inst?: string }>;
}) {
  const sp = await searchParams;
  const { accounts } = await loadPortfolioSnapshot({
    ownership: sp.own,
    institution: sp.inst,
  });
  const accountIds = accountIdsForInstitution(
    accounts,
    sp.inst && sp.inst !== "전체" ? sp.inst : null
  );
  const flows = await loadAssetFlows(accountIds);

  const inflow = flows.reduce((s, f) => s + Math.max(Number(f.amount) || 0, 0), 0);
  const outflow = flows.reduce(
    (s, f) => s + Math.max(-(Number(f.amount) || 0), 0),
    0
  );
  const trades = flows.filter((f) => f.flow_kind === "trade").length;

  const byMonthIn = aggregateByMonth(
    flows.map((f) => ({
      date: String(f.event_date).slice(0, 10),
      value: Math.max(Number(f.amount) || 0, 0),
      key: "in",
    }))
  );
  const byMonthOut = aggregateByMonth(
    flows.map((f) => ({
      date: String(f.event_date).slice(0, 10),
      value: Math.max(-(Number(f.amount) || 0), 0),
      key: "out",
    }))
  );
  const months = [
    ...new Set([...byMonthIn, ...byMonthOut].map((m) => m.month)),
  ]
    .sort()
    .slice(-12);
  const netBars = months.map((month) => {
    const inn = byMonthIn.find((m) => m.month === month)?.value || 0;
    const out = byMonthOut.find((m) => m.month === month)?.value || 0;
    return { label: month.slice(5), value: inn - out };
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-extrabold tracking-tight">거래</h1>
        <p className="mt-1 text-sm text-muted">자금 이동 · 원장</p>
      </div>

      <Suspense fallback={null}>
        <PortfolioFilters accounts={accounts} />
      </Suspense>

      <div className="grid grid-cols-2 gap-2">
        {(
          [
            ["유입", inflow],
            ["유출", outflow],
            ["순이동", inflow - outflow],
            ["매매 건수", trades],
          ] as const
        ).map(([label, v]) => (
          <div
            key={label}
            className="rounded-2xl border border-line bg-surface px-3 py-3 shadow-soft"
          >
            <div className="text-[11px] font-semibold text-muted">{label}</div>
            <div className="mt-1 text-sm font-extrabold tracking-tight">
              {label === "매매 건수" ? `${v}건` : fmtKrw(v, { signed: label === "순이동" })}
            </div>
          </div>
        ))}
      </div>

      <SimpleBarChart title="월별 순 자금 이동" bars={netBars} signed />

      <section className="overflow-hidden rounded-2xl border border-line bg-surface">
        <div className="border-b border-line px-4 py-3 text-sm font-extrabold">
          거래 원장
        </div>
        {flows.slice(0, 50).map((f, i) => {
          const amount = Number(f.amount) || 0;
          const dir = amount >= 0 ? "유입" : "유출";
          return (
            <div
              key={`${f.event_date}-${f.asset_ref}-${i}`}
              className="flex items-start justify-between gap-3 border-b border-line px-4 py-3 last:border-b-0"
            >
              <div className="min-w-0">
                <div className="text-sm font-extrabold tracking-tight">
                  {f.asset_ref || FLOW_KIND_KO[f.flow_kind] || f.flow_kind}
                </div>
                <div className="text-xs text-muted">
                  {String(f.event_date).slice(0, 10)} ·{" "}
                  {FLOW_KIND_KO[f.flow_kind] || f.flow_kind} · {dir}
                  {f.memo ? ` · ${f.memo}` : ""}
                </div>
              </div>
              <div className="shrink-0 text-sm font-extrabold">
                {fmtKrw(Math.abs(amount))}
              </div>
            </div>
          );
        })}
        {!flows.length ? (
          <p className="px-4 py-8 text-center text-sm text-muted">
            거래 데이터가 없습니다. 매매·배당·현금을 기록하면 여기에 쌓입니다.
          </p>
        ) : null}
      </section>
    </div>
  );
}
