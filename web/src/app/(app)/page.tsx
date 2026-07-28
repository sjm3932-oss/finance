import { Suspense } from "react";
import Link from "next/link";
import { NetWorthHero } from "@/components/NetWorthHero";
import { HoldingList } from "@/components/HoldingList";
import { PortfolioFilters } from "@/components/PortfolioFilters";
import { MonthlySummaryCard } from "@/components/MonthlySummaryCard";
import { AllocationDriftTable } from "@/components/AllocationDriftTable";
import { AlertBanners } from "@/components/AlertBanners";
import { NetWorthTrend } from "@/components/NetWorthTrend";
import { loadPortfolioSnapshot } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ own?: string; inst?: string }>;
}) {
  const sp = await searchParams;
  const {
    nw,
    returnPct,
    byTicker,
    latestSnap,
    institutions,
    monthly,
    allocation,
    alerts,
    snaps,
  } = await loadPortfolioSnapshot({
    ownership: sp.own,
    institution: sp.inst,
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-extrabold tracking-tight">홈</h1>
        <p className="mt-1 text-sm text-muted">
          순자산 한눈에 · 입력은 Streamlit 기록하기
        </p>
      </div>

      <Suspense fallback={null}>
        <PortfolioFilters institutions={institutions} />
      </Suspense>

      <AlertBanners alerts={alerts} />

      <NetWorthHero nw={nw} returnPct={returnPct} />

      {latestSnap?.snapshot_date ? (
        <p className="text-xs text-muted">
          최근 스냅샷 {String(latestSnap.snapshot_date)} · 저장 순자산{" "}
          {Number(latestSnap.net_assets || 0).toLocaleString("ko-KR")}원
        </p>
      ) : null}

      <MonthlySummaryCard monthly={monthly} />
      <AllocationDriftTable rows={allocation} />
      <NetWorthTrend snaps={snaps} />

      <section className="space-y-3">
        <div className="flex items-end justify-between">
          <h2 className="text-base font-extrabold tracking-tight">보유 미리보기</h2>
          <Link href="/holdings" className="text-sm font-semibold text-brand">
            전체
          </Link>
        </div>
        <HoldingList items={byTicker.slice(0, 8)} />
      </section>

      <div className="flex gap-3 text-sm font-semibold">
        <Link href="/more/net-worth" className="text-brand">
          순자산 구성
        </Link>
        <Link href="/more/other-assets" className="text-brand">
          기타자산
        </Link>
      </div>
    </div>
  );
}
