import Link from "next/link";
import { loadWatchlist } from "@/lib/data-insights";

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
        <p className="mt-1 text-sm text-muted">읽기 전용 · 등록은 Streamlit</p>
      </div>

      {alerts.length ? (
        <div className="space-y-2">
          {alerts.map((a) => (
            <div
              key={a.id}
              className="rounded-2xl border border-line bg-surface px-4 py-3 shadow-soft"
            >
              <div className="text-sm font-extrabold">
                {a.alert_kind === "stop" ? "손절가 도달" : "목표가 도달"} ·{" "}
                {a.ticker}
              </div>
              <div className="mt-1 text-xs text-muted">
                트리거 {a.trigger_price} · 시장 {a.market_price}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      <section className="overflow-hidden rounded-2xl border border-line bg-surface">
        {items.map((it) => (
          <div
            key={it.id}
            className="flex justify-between gap-3 border-b border-line px-4 py-3.5 last:border-b-0"
          >
            <div>
              <div className="text-sm font-extrabold">{it.name || it.ticker}</div>
              <div className="text-xs text-muted">
                {it.ticker}
                {it.note ? ` · ${it.note}` : ""}
              </div>
            </div>
            <div className="text-right text-xs font-bold text-muted">
              <div>현재 {it.price ?? "—"}</div>
              <div>목표 {it.target_price ?? "—"}</div>
              <div>손절 {it.stop_price ?? "—"}</div>
            </div>
          </div>
        ))}
        {!items.length ? (
          <p className="px-4 py-8 text-center text-sm text-muted">
            관심종목이 없습니다.
          </p>
        ) : null}
      </section>
    </div>
  );
}
