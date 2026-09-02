import { Suspense } from "react";
import Link from "next/link";
import { PortfolioFilters } from "@/components/PortfolioFilters";
import { DepositsPanel } from "@/components/DepositsPanel";
import { loadPortfolioSnapshot } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function DepositsPage({
  searchParams,
}: {
  searchParams: Promise<{ own?: string; inst?: string; sub?: string }>;
}) {
  const sp = await searchParams;
  const { deposits, accounts } = await loadPortfolioSnapshot({
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
          / 예적금
        </p>
        <h1 className="mt-1 text-xl font-extrabold tracking-tight">예적금</h1>
        <p className="mt-1 text-sm text-muted">
          적금·청약은 월 납입액으로 오늘 잔액을 자동 계산합니다.{" "}
          <Link href="/record?tab=deposit" className="font-semibold text-brand">
            기록에서 편집
          </Link>
        </p>
      </div>

      <Suspense fallback={null}>
        <PortfolioFilters accounts={accounts} />
      </Suspense>

      <DepositsPanel rows={deposits} />
    </div>
  );
}
