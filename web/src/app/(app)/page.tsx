import { Suspense } from "react";
import Link from "next/link";
import { NetWorthHero } from "@/components/NetWorthHero";
import { HoldingList } from "@/components/HoldingList";
import { PortfolioFilters } from "@/components/PortfolioFilters";
import { MonthlySummaryCard } from "@/components/MonthlySummaryCard";
import { AlertBanners } from "@/components/AlertBanners";
import { NetWorthTrend } from "@/components/NetWorthTrend";
import { AllocationTreemap } from "@/components/AllocationTreemap";
import { PeriodChangeRow } from "@/components/PeriodChangeRow";
import { loadPortfolioSnapshot } from "@/lib/data";
import {
  loadPeriodChange,
  loadBenchmarkSeries,
  loadRealizedRows,
} from "@/lib/data-insights";
import { fmtKrw } from "@/lib/money";
import { accountIdsForInstitution } from "@/lib/portfolio";

export const dynamic = "force-dynamic";

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ own?: string; inst?: string }>;
}) {
  const sp = await searchParams;
  const snap = await loadPortfolioSnapshot({
    ownership: sp.own,
    institution: sp.inst,
  });
  const {
    nw,
    returnPct,
    byTicker,
    latestSnap,
    monthly,
    alerts,
    snaps,
    live,
    accounts,
  } = snap;

  const accountIds = accountIdsForInstitution(
    accounts,
    sp.inst && sp.inst !== "전체" ? sp.inst : null
  );

  const [period, benchmark, realized] = await Promise.all([
    loadPeriodChange(nw.invest, accountIds),
    loadBenchmarkSeries(snaps, "sp500"),
    loadRealizedRows(snap.usdkrw, accountIds),
  ]);

  const ytdRealized = realized
    .filter((r) => r.event_date.startsWith(String(new Date().getFullYear())))
    .reduce((s, r) => s + r.pnl_krw, 0);
  const unrealized = live.reduce((s, r) => {
    const v = r.value_krw || 0;
    const c = r.cost_krw || 0;
    return s + (v - c);
  }, 0);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-extrabold tracking-tight">홈</h1>
        <p className="mt-1 text-sm text-muted">순자산 · 추이 · 손익 요약</p>
      </div>

      <Suspense fallback={null}>
        <PortfolioFilters accounts={accounts} />
      </Suspense>

      <AlertBanners alerts={alerts} />
      <PeriodChangeRow period={period} />
      <NetWorthHero nw={nw} returnPct={returnPct} />

      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-2xl border border-line bg-surface px-3 py-3 shadow-soft">
          <div className="text-[11px] font-semibold text-muted">미실현 손익</div>
          <div className="mt-1 text-sm font-extrabold tracking-tight">
            {fmtKrw(unrealized, { signed: true })}
          </div>
        </div>
        <div className="rounded-2xl border border-line bg-surface px-3 py-3 shadow-soft">
          <div className="text-[11px] font-semibold text-muted">실현 손익 YTD</div>
          <div className="mt-1 text-sm font-extrabold tracking-tight">
            {fmtKrw(ytdRealized, { signed: true })}
          </div>
        </div>
      </div>

      {latestSnap?.snapshot_date ? (
        <p className="text-xs text-muted">
          최근 스냅샷 {String(latestSnap.snapshot_date)} · 저장 순자산{" "}
          {Number(latestSnap.net_assets || 0).toLocaleString("ko-KR")}원
        </p>
      ) : null}

      <MonthlySummaryCard monthly={monthly} />
      <AllocationTreemap live={live} />
      <NetWorthTrend snaps={snaps} benchmark={benchmark} />

      <section className="space-y-3">
        <div className="flex items-end justify-between">
          <h2 className="text-base font-extrabold tracking-tight">보유 미리보기</h2>
          <Link href="/holdings" className="text-sm font-semibold text-brand">
            전체
          </Link>
        </div>
        <HoldingList
          items={byTicker.slice(0, 8)}
          linkable
          query={
            [
              sp.own ? `own=${encodeURIComponent(sp.own)}` : "",
              sp.inst ? `inst=${encodeURIComponent(sp.inst)}` : "",
            ]
              .filter(Boolean)
              .join("&")
          }
        />
      </section>

      <div className="flex flex-wrap gap-3 text-sm font-semibold">
        <Link href="/record?tab=toss" className="text-brand">
          토스 동기화
        </Link>
        <Link href="/pnl" className="text-brand">
          손익
        </Link>
        <Link href="/flows" className="text-brand">
          거래
        </Link>
        <Link href="/more/net-worth" className="text-brand">
          순자산 구성
        </Link>
      </div>
    </div>
  );
}
