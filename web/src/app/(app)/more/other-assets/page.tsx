import { Suspense } from "react";
import Link from "next/link";
import { PortfolioFilters } from "@/components/PortfolioFilters";
import { OtherAssetsPanel } from "@/components/OtherAssetsPanel";
import { loadPortfolioSnapshot } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function OtherAssetsPage({
  searchParams,
}: {
  searchParams: Promise<{ own?: string; inst?: string }>;
}) {
  const sp = await searchParams;
  const { otherAssets, institutions } = await loadPortfolioSnapshot({
    ownership: sp.own,
    institution: sp.inst,
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
          부동산 · 연금 · 보험 · 예적금 등
        </p>
      </div>

      <Suspense fallback={null}>
        <PortfolioFilters institutions={institutions} />
      </Suspense>

      <OtherAssetsPanel rows={otherAssets} />
    </div>
  );
}
