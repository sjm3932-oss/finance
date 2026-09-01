import { HoldingList } from "@/components/HoldingList";
import { PortfolioFilters } from "@/components/PortfolioFilters";
import { Suspense } from "react";
import { fmtKrw, fmtPct } from "@/lib/money";
import { loadPortfolioSnapshot } from "@/lib/data";
import { filterQuery } from "@/lib/portfolio";

export const dynamic = "force-dynamic";

export default async function HoldingsPage({
  searchParams,
}: {
  searchParams: Promise<{ own?: string; inst?: string; sub?: string }>;
}) {
  const sp = await searchParams;
  const { byTicker, nw, returnPct, accounts } = await loadPortfolioSnapshot({
    ownership: sp.own,
    institution: sp.inst,
    sub: sp.sub,
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-extrabold tracking-tight">보유</h1>
        <p className="mt-1 text-sm text-muted">
          투자자산 {fmtKrw(nw.invest)} · 수익률 {fmtPct(returnPct)} · 종목 탭으로
          상세
        </p>
      </div>
      <Suspense fallback={null}>
        <PortfolioFilters accounts={accounts} />
      </Suspense>
      <HoldingList
        items={byTicker}
        linkable
        query={filterQuery(sp)}
      />
    </div>
  );
}
