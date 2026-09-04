import { Suspense } from "react";
import Link from "next/link";
import { PortfolioFilters } from "@/components/PortfolioFilters";
import { PeriodChips, SimpleBarChart, TimeSeriesBarChart } from "@/components/Charts";
import { SignedAmount } from "@/components/SignedValue";
import { loadPortfolioSnapshot } from "@/lib/data";
import {
  loadRealizedRows,
  loadDividendInsights,
} from "@/lib/data-insights";
import { accountIdsForInstitution } from "@/lib/portfolio";
import { aggregateByMonth, PNL_KIND_KO, toKrwAmount } from "@/lib/insights";
import { todayKst } from "@/lib/dates";
import {
  LAST_12M,
  fillMonthSeries,
  formatMonthTick,
  monthInPeriod,
  monthKeysForPeriod,
  parsePeriodWindow,
  periodLabel,
  periodOptions,
  yearsFromMonthKeys,
} from "@/lib/month-window";

export const dynamic = "force-dynamic";

export default async function PnlPage({
  searchParams,
}: {
  searchParams: Promise<{
    own?: string;
    inst?: string;
    tab?: string;
    sub?: string;
    year?: string;
    period?: string;
  }>;
}) {
  const sp = await searchParams;
  const tab = sp.tab === "dividend" ? "dividend" : "realized";
  const { accounts, usdkrw } = await loadPortfolioSnapshot({
    ownership: sp.own,
    institution: sp.inst,
    sub: sp.sub,
  });
  const accountIds = accountIdsForInstitution(
    accounts,
    sp.inst && sp.inst !== "전체" ? sp.inst : null,
    sp.sub && sp.sub !== "전체" ? sp.sub : null
  );

  const [realized, div] = await Promise.all([
    loadRealizedRows(usdkrw, accountIds),
    loadDividendInsights(usdkrw, accountIds),
  ]);

  const nowYm = todayKst().slice(0, 7);
  const years = yearsFromMonthKeys([
    ...realized.map((r) => r.event_date),
    ...div.rows.map((r) => String(r.pay_date)),
  ]);
  const period = parsePeriodWindow(sp.period || sp.year, years, nowYm);
  const monthKeys = monthKeysForPeriod(period, nowYm);
  const includeYear = new Set(monthKeys.map((m) => m.slice(0, 4))).size > 1;
  const realizedInPeriod = realized.filter((r) =>
    monthInPeriod(r.event_date, monthKeys)
  );
  const dividendsInPeriod = div.rows.filter((r) =>
    monthInPeriod(String(r.pay_date), monthKeys)
  );

  const total = realizedInPeriod.reduce((s, r) => s + r.pnl_krw, 0);
  const byKind = Object.keys(PNL_KIND_KO).map((k) => ({
    label: PNL_KIND_KO[k],
    value: realizedInPeriod
      .filter((r) => r.pnl_kind === k)
      .reduce((s, r) => s + r.pnl_krw, 0),
  }));

  const realizedMonthly = aggregateByMonth(
    realizedInPeriod.map((r) => ({ date: r.event_date, value: r.pnl_krw }))
  );
  const dividendMonthly = aggregateByMonth(
    dividendsInPeriod.map((r) => ({
      date: String(r.pay_date),
      value: toKrwAmount(Number(r.amount || 0), r.currency, usdkrw),
    }))
  );
  const monthlyBars = fillMonthSeries(realizedMonthly, monthKeys).map((m) => ({
    key: m.month,
    label: formatMonthTick(m.month, includeYear),
    value: m.value,
  }));
  const dividendBars = fillMonthSeries(dividendMonthly, monthKeys).map((m) => ({
    key: m.month,
    label: formatMonthTick(m.month, includeYear),
    value: m.value,
  }));

  const byTickerMap = new Map<string, number>();
  for (const r of realizedInPeriod) {
    const label = r.asset_name || r.asset_ref;
    byTickerMap.set(label, (byTickerMap.get(label) || 0) + r.pnl_krw);
  }
  const byTicker = [...byTickerMap.entries()]
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, 12);

  const q = new URLSearchParams();
  if (sp.own) q.set("own", sp.own);
  if (sp.inst) q.set("inst", sp.inst);
  if (sp.sub) q.set("sub", sp.sub);
  if (period !== LAST_12M) q.set("period", period);

  function hrefFor(next: { tab?: string; period?: string }) {
    const nextQ = new URLSearchParams(q);
    const nextTab = next.tab ?? tab;
    if (nextTab === "dividend") nextQ.set("tab", "dividend");
    else nextQ.delete("tab");
    const nextPeriod = next.period ?? period;
    if (nextPeriod === LAST_12M) nextQ.delete("period");
    else nextQ.set("period", nextPeriod);
    nextQ.delete("year");
    const s = nextQ.toString();
    return s ? `/pnl?${s}` : "/pnl";
  }

  const periodChips = periodOptions(years, nowYm).map((w) => ({
    id: w.id,
    label: w.label,
    href: hrefFor({ period: w.id }),
    active: w.id === period,
  }));
  const selectedPeriodLabel = periodLabel(period, nowYm);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-extrabold tracking-tight">손익</h1>
        <p className="mt-1 text-sm text-muted">실현손익 · 배당</p>
      </div>

      <Suspense fallback={null}>
        <PortfolioFilters accounts={accounts} />
      </Suspense>

      <div className="flex gap-1.5">
        <Link
          href={hrefFor({ tab: "realized" })}
          className={`rounded-lg px-3 py-1.5 text-xs font-bold ${
            tab === "realized" ? "bg-brand text-white" : "bg-surface text-muted ring-1 ring-line"
          }`}
        >
          실현손익
        </Link>
        <Link
          href={hrefFor({ tab: "dividend" })}
          className={`rounded-lg px-3 py-1.5 text-xs font-bold ${
            tab === "dividend" ? "bg-brand text-white" : "bg-surface text-muted ring-1 ring-line"
          }`}
        >
          배당
        </Link>
      </div>

      {tab === "realized" ? (
        <>
          <div className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
            <div className="text-xs font-semibold text-muted">기간 실현손익</div>
            <PeriodChips windows={periodChips} />
            <p className="mt-2 text-[11px] font-semibold text-muted">
              {selectedPeriodLabel}
            </p>
            <div className="mt-1">
              <SignedAmount amount={total} className="text-2xl" />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              {byKind.map((k) => (
                <div key={k.label}>
                  <div className="text-[11px] text-muted">{k.label}</div>
                  <SignedAmount amount={k.value} className="text-sm" />
                </div>
              ))}
            </div>
          </div>
          <TimeSeriesBarChart
            title="월별 실현손익"
            subtitle={selectedPeriodLabel}
            bars={monthlyBars}
            signed
          />
          <SimpleBarChart title="종목별 실현손익" bars={byTicker} signed />
          <section className="overflow-hidden rounded-2xl border border-line bg-surface">
            <div className="border-b border-line px-4 py-3 text-sm font-extrabold">
              실현 원장
            </div>
            {realizedInPeriod.slice(0, 40).map((r, i) => (
              <div
                key={`${r.event_date}-${r.asset_ref}-${i}`}
                className="flex items-start justify-between gap-3 border-b border-line px-4 py-3 last:border-b-0"
              >
                <div className="min-w-0">
                  <div className="text-sm font-extrabold tracking-tight">
                    {r.asset_name}
                  </div>
                  <div className="text-xs text-muted">
                    {r.event_date} · {r.pnl_kind_ko} · {r.detail}
                  </div>
                </div>
                <div className="shrink-0">
                  <SignedAmount amount={r.pnl_krw} className="text-sm" />
                </div>
              </div>
            ))}
            {!realizedInPeriod.length ? (
              <p className="px-4 py-8 text-center text-sm text-muted">
                실현손익 데이터가 없습니다.
              </p>
            ) : null}
          </section>
        </>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2">
            {(
              [
                ["이번 달 배당", div.stats.month_krw],
                ["올해 배당", div.stats.ytd_krw],
                ["예상 월 배당", div.stats.expected_krw],
                ["최근 12개월 평균", div.stats.avg_month_krw],
              ] as const
            ).map(([label, v]) => (
              <div
                key={label}
                className="rounded-2xl border border-line bg-surface px-3 py-3 shadow-soft"
              >
                <div className="text-[11px] font-semibold text-muted">{label}</div>
                <div className="mt-1">
                  <SignedAmount amount={v} className="text-sm" />
                </div>
              </div>
            ))}
          </div>
          <TimeSeriesBarChart
            title="월별 배당 수입"
            subtitle={selectedPeriodLabel}
            bars={dividendBars}
            windows={periodChips}
            signed
          />
          <section className="overflow-hidden rounded-2xl border border-line bg-surface">
            <div className="border-b border-line px-4 py-3 text-sm font-extrabold">
              최근 배당
            </div>
            {div.rows.slice(0, 40).map((r, i) => (
              <div
                key={`${r.pay_date}-${r.ticker}-${i}`}
                className="flex items-start justify-between gap-3 border-b border-line px-4 py-3 last:border-b-0"
              >
                <div>
                  <div className="text-sm font-extrabold">
                    {r.name || r.ticker}
                  </div>
                  <div className="text-xs text-muted">
                    {String(r.pay_date).slice(0, 10)} · {r.ticker}
                  </div>
                </div>
                <div className="shrink-0">
                  <SignedAmount
                    amount={Number(r.amount)}
                    currency={r.currency}
                    className="text-sm"
                  />
                </div>
              </div>
            ))}
            {!div.rows.length ? (
              <p className="px-4 py-8 text-center text-sm text-muted">
                배당 내역이 없습니다.
              </p>
            ) : null}
          </section>
        </>
      )}
    </div>
  );
}
