import Link from "next/link";
import { SignedAmount, SignedPct } from "@/components/SignedValue";
import { fmtKrw } from "@/lib/money";
import {
  ASSET_KIND_KO,
  OWNERSHIP_KO,
  groupOtherByKind,
  otherAssetReturn,
  type OtherAssetRow,
} from "@/lib/portfolio";

export function OtherAssetsPanel({
  rows,
  showBreakdown = true,
}: {
  rows: OtherAssetRow[];
  showBreakdown?: boolean;
}) {
  const total = rows.reduce((s, r) => s + Number(r.value_krw || 0), 0);
  const byKind = groupOtherByKind(rows);
  const withCost = rows.filter((r) => Number(r.cost_krw) > 0);
  const costSum = withCost.reduce((s, r) => s + Number(r.cost_krw || 0), 0);
  const valueOnCost = withCost.reduce((s, r) => s + Number(r.value_krw || 0), 0);
  const totalPnl = costSum > 0 ? valueOnCost - costSum : null;
  const totalPct = costSum > 0 ? (100 * (valueOnCost - costSum)) / costSum : null;

  if (!rows.length) {
    return (
      <div className="rounded-2xl border border-dashed border-line bg-surface px-4 py-8 text-center text-sm text-muted">
        등록된 기타자산이 없습니다.{" "}
        <Link href="/record?tab=wealth" className="font-semibold text-brand">
          기록하기 → 부동산·기타
        </Link>
        에서 부동산·연금 등을 추가하세요.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
        <p className="text-xs font-semibold text-muted">기타자산 시세 합계</p>
        <p className="mt-1 text-2xl font-extrabold tracking-tight">
          {fmtKrw(total)}
        </p>
        {totalPnl !== null ? (
          <div className="mt-2 flex flex-wrap items-baseline gap-x-3 text-xs font-bold">
            <span className="text-muted">매수가 {fmtKrw(costSum)}</span>
            <span className="inline-flex items-baseline gap-1">
              손익
              <SignedAmount amount={totalPnl} className="text-xs" />
              <span className="text-muted">·</span>
              <SignedPct value={totalPct} />
            </span>
          </div>
        ) : null}
        {showBreakdown && byKind.length ? (
          <div className="mt-3 space-y-2 border-t border-line pt-3">
            {byKind.map((k) => (
              <div key={k.kind} className="flex items-center justify-between text-sm">
                <span className="font-semibold text-muted">{k.label}</span>
                <span className="font-extrabold tracking-tight">
                  {fmtKrw(k.value)}
                  <span className="ml-2 text-xs font-bold text-muted">
                    {k.pct.toFixed(0)}%
                  </span>
                </span>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      <div className="overflow-hidden rounded-2xl border border-line bg-surface">
        {rows
          .slice()
          .sort((a, b) => Number(b.value_krw || 0) - Number(a.value_krw || 0))
          .map((r, i) => {
            const ret = otherAssetReturn(r);
            return (
              <div
                key={r.id || `${r.name}-${i}`}
                className="border-b border-line px-4 py-3.5 last:border-b-0"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-[15px] font-extrabold tracking-tight">
                      {r.name || "기타자산"}
                    </div>
                    <div className="mt-0.5 text-xs text-muted">
                      {ASSET_KIND_KO[r.asset_kind || ""] || r.asset_kind || "기타"}
                      {" · "}
                      {OWNERSHIP_KO[r.ownership || "joint"] || "공동"}
                      {ret.cost !== null
                        ? ` · 매수 ${fmtKrw(ret.cost)}`
                        : ""}
                    </div>
                    {r.memo ? (
                      <p className="mt-1 text-xs text-muted">{r.memo}</p>
                    ) : null}
                  </div>
                  <div className="shrink-0 text-right">
                    <div className="text-[15px] font-extrabold tracking-tight">
                      {fmtKrw(r.value_krw)}
                    </div>
                    {ret.pct !== null ? (
                      <div className="mt-0.5 flex flex-wrap items-baseline justify-end gap-1">
                        <SignedAmount amount={ret.pnl} className="text-xs" />
                        <span className="text-xs font-bold text-muted">·</span>
                        <SignedPct value={ret.pct} />
                      </div>
                    ) : (
                      <div className="text-xs font-bold text-muted">시세</div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
      </div>
    </div>
  );
}
