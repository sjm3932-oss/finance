import Link from "next/link";
import { fmtKrw } from "@/lib/money";
import {
  DEPOSIT_KIND_KO,
  OWNERSHIP_KO,
  depositBalance,
  depositExpectedInterest,
  installmentProgress,
  type DepositRow,
} from "@/lib/portfolio";

export function DepositsPanel({ rows }: { rows: DepositRow[] }) {
  const total = rows.reduce((s, r) => s + depositBalance(r), 0);

  if (!rows.length) {
    return (
      <div className="rounded-2xl border border-dashed border-line bg-surface px-4 py-8 text-center text-sm text-muted">
        등록된 예적금이 없습니다.{" "}
        <Link href="/record?tab=deposit" className="font-semibold text-brand">
          기록하기 → 예적금
        </Link>
        에서 적금은 월 납입액, 예금은 원금·이율·만기를 추가하세요.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
        <p className="text-xs font-semibold text-muted">예적금 합계</p>
        <p className="mt-1 text-2xl font-extrabold tracking-tight">{fmtKrw(total)}</p>
      </div>
      <div className="overflow-hidden rounded-2xl border border-line bg-surface">
        {rows
          .slice()
          .sort((a, b) => depositBalance(b) - depositBalance(a))
          .map((r, i) => {
            const expected = depositExpectedInterest(r);
            const rate = Number(r.interest_rate || 0);
            const maturity = r.maturity_date
              ? String(r.maturity_date).slice(0, 10)
              : null;
            const prog = installmentProgress(r);
            return (
              <div
                key={r.id || `${r.name}-${i}`}
                className="border-b border-line px-4 py-3.5 last:border-b-0"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-[15px] font-extrabold tracking-tight">
                      {r.name || "예적금"}
                    </div>
                    <div className="mt-0.5 text-xs text-muted">
                      {r.institution || "금융기관"}
                      {" · "}
                      {DEPOSIT_KIND_KO[r.deposit_kind || ""] || r.deposit_kind || "예적금"}
                      {" · "}
                      {OWNERSHIP_KO[r.ownership || "joint"] || "공동"}
                      {prog
                        ? ` · ${prog.paymentsMade}/${prog.paymentsTotal}회 · 월 ${fmtKrw(prog.monthly)}`
                        : ""}
                      {rate > 0 ? ` · 연 ${rate}%` : ""}
                      {maturity ? ` · 만기 ${maturity}` : ""}
                    </div>
                    {r.memo ? (
                      <p className="mt-1 text-xs text-muted">{r.memo}</p>
                    ) : null}
                  </div>
                  <div className="shrink-0 text-right">
                    <div className="text-[15px] font-extrabold tracking-tight">
                      {fmtKrw(depositBalance(r))}
                    </div>
                    {(() => {
                      if (prog) {
                        return (
                          <div className="text-xs font-bold text-muted">
                            만기≈{fmtKrw(prog.maturityValue)}
                          </div>
                        );
                      }
                      if (expected != null) {
                        return (
                          <div className="text-xs font-bold text-muted">
                            만기이자≈{fmtKrw(expected)}
                          </div>
                        );
                      }
                      return <div className="text-xs font-bold text-muted">잔액</div>;
                    })()}
                  </div>
                </div>
              </div>
            );
          })}
      </div>
    </div>
  );
}
