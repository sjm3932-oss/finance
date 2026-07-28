import Link from "next/link";
import { loadWatchlist } from "@/lib/data-insights";
import { WatchlistForms } from "@/components/WatchlistForms";

export const dynamic = "force-dynamic";

export default async function WatchlistPage() {
  const { items, alerts } = await loadWatchlist();

  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-bold text-muted">
          <Link href="/more" className="text-brand">
            더보기
          </Link>{" "}
          / 관심
        </p>
        <h1 className="mt-1 text-xl font-extrabold tracking-tight">관심종목</h1>
        <p className="mt-1 text-sm text-muted">등록 · 목표가/손절 · 알림 검사</p>
      </div>
      <WatchlistForms items={items} alerts={alerts} />
    </div>
  );
}
