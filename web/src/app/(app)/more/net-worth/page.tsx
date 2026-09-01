import { Suspense } from "react";
import Link from "next/link";
import { NetWorthHero } from "@/components/NetWorthHero";
import { PortfolioFilters } from "@/components/PortfolioFilters";
import { CashAccountsPanel } from "@/components/CashAccountsPanel";
import { OtherAssetsPanel } from "@/components/OtherAssetsPanel";
import { loadPortfolioSnapshot } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function NetWorthPage({
  searchParams,
}: {
  searchParams: Promise<{ own?: string; inst?: string; sub?: string }>;
}) {
  const sp = await searchParams;
  const {
    nw,
    returnPct,
    accounts,
    cashAccounts,
    otherAssets,
  } = await loadPortfolioSnapshot({
    ownership: sp.own,
    institution: sp.inst,
    sub: sp.sub,
  });

  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-bold text-muted">
          <Link href="/more" className="text-brand">
            더보기
          </Link>{" "}
          / 순자산
        </p>
        <h1 className="mt-1 text-xl font-extrabold tracking-tight">순자산 구성</h1>
        <p className="mt-1 text-sm text-muted">
          투자 · 현금 · 기타 · 부채 상세
        </p>
      </div>

      <Suspense fallback={null}>
        <PortfolioFilters accounts={accounts} />
      </Suspense>

      <NetWorthHero nw={nw} returnPct={returnPct} />

      <section className="space-y-3">
        <h2 className="text-base font-extrabold tracking-tight">현금 · 계좌</h2>
        <CashAccountsPanel rows={cashAccounts} />
      </section>

      <section className="space-y-3">
        <div className="flex items-end justify-between">
          <h2 className="text-base font-extrabold tracking-tight">기타자산</h2>
          <Link
            href="/more/other-assets"
            className="text-sm font-semibold text-brand"
          >
            전체
          </Link>
        </div>
        <OtherAssetsPanel rows={otherAssets} showBreakdown={false} />
      </section>
    </div>
  );
}
