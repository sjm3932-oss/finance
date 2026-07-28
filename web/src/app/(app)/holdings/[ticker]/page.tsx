import Link from "next/link";
import { loadPortfolioSnapshot } from "@/lib/data";
import { loadTickerHistory } from "@/lib/data-insights";
import { accountIdsForInstitution } from "@/lib/portfolio";
import { fmtKrw } from "@/lib/money";
import { NetWorthTrend } from "@/components/NetWorthTrend";

export const dynamic = "force-dynamic";

export default async function HoldingDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ ticker: string }>;
  searchParams: Promise<{ inst?: string }>;
}) {
  const { ticker: raw } = await params;
  const ticker = decodeURIComponent(raw);
  const sp = await searchParams;
  const { byTicker, accounts, live } = await loadPortfolioSnapshot({
    institution: sp.inst,
  });
  const accountIds = accountIdsForInstitution(
    accounts,
    sp.inst && sp.inst !== "전체" ? sp.inst : null
  );
  const agg = byTicker.find((t) => t.ticker === ticker);
  const rows = live.filter((r) => r.ticker === ticker);
  const hist = await loadTickerHistory(ticker, accountIds);

  const snaps = hist.valueTrend.map((p) => ({
    snapshot_date: p.date,
    net_assets: p.value,
  }));

  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-bold text-muted">
          <Link href="/holdings" className="text-brand">
            보유
          </Link>{" "}
          / {ticker}
        </p>
        <h1 className="mt-1 text-xl font-extrabold tracking-tight">
          {agg?.name || ticker}
        </h1>
        <p className="mt-1 text-sm text-muted">
          {fmtKrw(agg?.value_krw)} · {agg?.qty?.toLocaleString("ko-KR")}주
        </p>
      </div>

      {rows.length > 1 ? (
        <section className="overflow-hidden rounded-2xl border border-line bg-surface">
          <div className="border-b border-line px-4 py-3 text-sm font-extrabold">
            계좌별
          </div>
          {rows.map((r) => (
            <div
              key={r.account_id}
              className="flex justify-between border-b border-line px-4 py-3 last:border-b-0"
            >
              <div>
                <div className="text-sm font-extrabold">{r.institution}</div>
                <div className="text-xs text-muted">
                  {r.qty.toLocaleString("ko-KR")}주 · 평단 {r.avg}
                </div>
              </div>
              <div className="text-sm font-extrabold">{fmtKrw(r.value_krw)}</div>
            </div>
          ))}
        </section>
      ) : null}

      {snaps.length >= 2 ? (
        <NetWorthTrend snaps={snaps} title="평가액 추이" />
      ) : (
        <p className="text-sm text-muted">종목 평가액 추이 스냅샷이 아직 없습니다.</p>
      )}

      <section className="overflow-hidden rounded-2xl border border-line bg-surface">
        <div className="border-b border-line px-4 py-3 text-sm font-extrabold">
          매매 이력
        </div>
        {hist.trades.map((t, i) => (
          <div
            key={i}
            className="flex justify-between gap-3 border-b border-line px-4 py-3 last:border-b-0"
          >
            <div>
              <div className="text-sm font-extrabold">
                {t.trade_type === "sell" ? "매도" : "매수"}
              </div>
              <div className="text-xs text-muted">
                {String(t.trade_date).slice(0, 10)} · {String(t.quantity)} @{" "}
                {String(t.price)}
              </div>
            </div>
            <div className="text-right text-xs font-bold text-muted">
              {t.realized_pnl != null && t.realized_pnl !== undefined
                ? fmtKrw(Number(t.realized_pnl), { signed: true })
                : String(t.currency || "")}
            </div>
          </div>
        ))}
        {!hist.trades.length ? (
          <p className="px-4 py-6 text-center text-sm text-muted">매매 이력 없음</p>
        ) : null}
      </section>

      <section className="overflow-hidden rounded-2xl border border-line bg-surface">
        <div className="border-b border-line px-4 py-3 text-sm font-extrabold">
          배당 이력
        </div>
        {hist.dividends.map((d, i) => (
          <div
            key={i}
            className="flex justify-between border-b border-line px-4 py-3 last:border-b-0"
          >
            <div>
              <div className="text-sm font-extrabold">
                {String(d.pay_date).slice(0, 10)}
              </div>
              <div className="text-xs text-muted">{d.memo || "배당"}</div>
            </div>
            <div className="text-sm font-extrabold">
              {d.currency === "USD"
                ? `$${Number(d.amount).toLocaleString("en-US")}`
                : fmtKrw(d.amount)}
            </div>
          </div>
        ))}
        {!hist.dividends.length ? (
          <p className="px-4 py-6 text-center text-sm text-muted">배당 이력 없음</p>
        ) : null}
      </section>
    </div>
  );
}
