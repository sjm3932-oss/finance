import Link from "next/link";
import { NetWorthHero } from "@/components/NetWorthHero";
import { HoldingList } from "@/components/HoldingList";
import { loadPortfolioSnapshot } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const { nw, returnPct, byTicker, latestSnap } = await loadPortfolioSnapshot();

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-extrabold tracking-tight">요약</h1>
        <p className="mt-1 text-sm text-muted">
          Phase 0 읽기 전용 · 입력은 Streamlit 기록하기
        </p>
      </div>

      <NetWorthHero nw={nw} returnPct={returnPct} />

      {latestSnap?.snapshot_date ? (
        <p className="text-xs text-muted">
          최근 스냅샷 {String(latestSnap.snapshot_date)} · 저장 순자산{" "}
          {Number(latestSnap.net_assets || 0).toLocaleString("ko-KR")}원
        </p>
      ) : null}

      <section className="space-y-3">
        <div className="flex items-end justify-between">
          <h2 className="text-base font-extrabold tracking-tight">보유 미리보기</h2>
          <Link href="/holdings" className="text-sm font-semibold text-brand">
            전체
          </Link>
        </div>
        <HoldingList items={byTicker.slice(0, 8)} />
      </section>
    </div>
  );
}
