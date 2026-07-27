import { HoldingList } from "@/components/HoldingList";
import { fmtKrw, fmtPct } from "@/lib/money";
import { loadPortfolioSnapshot } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function HoldingsPage() {
  const { byTicker, nw, returnPct } = await loadPortfolioSnapshot();

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-extrabold tracking-tight">보유</h1>
        <p className="mt-1 text-sm text-muted">
          투자자산 {fmtKrw(nw.invest)} · 수익률 {fmtPct(returnPct)}
        </p>
      </div>
      <HoldingList items={byTicker} />
    </div>
  );
}
