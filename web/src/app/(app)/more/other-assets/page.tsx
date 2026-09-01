import { Suspense } from "react";
import Link from "next/link";
import { PortfolioFilters } from "@/components/PortfolioFilters";
import { OtherAssetsPanel } from "@/components/OtherAssetsPanel";
import { loadPortfolioSnapshot } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function OtherAssetsPage({
  searchParams,
}: {
  searchParams: Promise<{ own?: string; inst?: string; sub?: string }>;
}) {
  const sp = await searchParams;
  const { otherAssets, accounts } = await loadPortfolioSnapshot({
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
          / 기타자산
        </p>
        <h1 className="mt-1 text-xl font-extrabold tracking-tight">기타자산</h1>
        <p className="mt-1 text-sm text-muted">
          부동산 · 연금 · 보험 · 예적금 등 · 매수가 대비 수익률 ·{" "}
          <Link href="/record?tab=wealth" className="font-semibold text-brand">
            기록에서 편집
          </Link>
        </p>
      </div>

      <Suspense fallback={null}>
        <PortfolioFilters accounts={accounts} />
      </Suspense>

      <OtherAssetsPanel rows={otherAssets} />
    </div>
  );
}
