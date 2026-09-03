import { Suspense } from "react";
import { PortfolioFilters } from "@/components/PortfolioFilters";
import { MonthlyFlowChart } from "@/components/Charts";
import { FlowAmount } from "@/components/SignedValue";
import { loadPortfolioSnapshot } from "@/lib/data";
import { loadAssetFlows } from "@/lib/data-insights";
import { accountIdsForInstitution } from "@/lib/portfolio";
import { FLOW_KIND_KO, aggregateByMonth } from "@/lib/insights";
import { flowDisplayName, isTickerLike, normalizeKrTicker } from "@/lib/tickers";

export const dynamic = "force-dynamic";

export default async function FlowsPage({
  searchParams,
}: {
  searchParams: Promise<{ own?: string; inst?: string; sub?: string }>;
}) {
  const sp = await searchParams;
  const { accounts } = await loadPortfolioSnapshot({
    ownership: sp.own,
    institution: sp.inst,
    sub: sp.sub,
  });
  const accountIds = accountIdsForInstitution(
    accounts,
    sp.inst && sp.inst !== "전체" ? sp.inst : null,
    sp.sub && sp.sub !== "전체" ? sp.sub : null
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
  const monthFlows = months.map((month) => {
    const inn = byMonthIn.find((m) => m.month === month)?.value || 0;
    const out = byMonthOut.find((m) => m.month === month)?.value || 0;
    return {
      id: month,
      label: `${Number(month.slice(5))}월`,
      inflow: inn,
      outflow: out,
    };
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
        <div className="rounded-2xl border border-line bg-surface px-3 py-3 shadow-soft">
          <div className="text-[11px] font-semibold text-muted">유입</div>
          <div className="mt-1">
            <FlowAmount amount={inflow} />
          </div>
        </div>
        <div className="rounded-2xl border border-line bg-surface px-3 py-3 shadow-soft">
          <div className="text-[11px] font-semibold text-muted">유출</div>
          <div className="mt-1">
            <FlowAmount amount={-outflow} />
          </div>
        </div>
        <div className="rounded-2xl border border-line bg-surface px-3 py-3 shadow-soft">
          <div className="text-[11px] font-semibold text-muted">순이동</div>
          <div className="mt-1">
            <FlowAmount amount={inflow - outflow} signedNet />
          </div>
        </div>
        <div className="rounded-2xl border border-line bg-surface px-3 py-3 shadow-soft">
          <div className="text-[11px] font-semibold text-muted">매매 건수</div>
          <div className="mt-1 text-sm font-extrabold tracking-tight">{trades}건</div>
        </div>
      </div>

      <MonthlyFlowChart title="월별 자금 이동" months={monthFlows} />

      <section className="overflow-hidden rounded-2xl border border-line bg-surface">
        <div className="border-b border-line px-4 py-3 text-sm font-extrabold">
          거래 원장
        </div>
        {flows.slice(0, 50).map((f, i) => {
          const amount = Number(f.amount) || 0;
          const title = flowDisplayName(f, FLOW_KIND_KO);
          const ticker =
            f.asset_ref &&
            !isTickerLike(title) &&
            isTickerLike(f.asset_ref)
              ? normalizeKrTicker(f.asset_ref)
              : null;
          return (
            <div
              key={`${f.event_date}-${f.asset_ref}-${i}`}
              className="flex items-start justify-between gap-3 border-b border-line px-4 py-3 last:border-b-0"
            >
              <div className="min-w-0">
                <div className="text-sm font-extrabold tracking-tight">
                  {title}
                </div>
                <div className="text-xs text-muted">
                  {String(f.event_date).slice(0, 10)} ·{" "}
                  {FLOW_KIND_KO[f.flow_kind] || f.flow_kind}
                  {ticker ? ` · ${ticker}` : ""}
                  {f.memo ? ` · ${f.memo}` : ""}
                </div>
              </div>
              <div className="shrink-0">
                <FlowAmount amount={amount} />
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
