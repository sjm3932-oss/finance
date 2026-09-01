import { fmtKrw } from "@/lib/money";
import { accountProductCode, accountSubLabel, OWNERSHIP_KO } from "@/lib/portfolio";

type CashAccount = {
  id: string;
  institution: string;
  account_type: string;
  ownership: string;
  currency: string;
  cash_balance: number;
  memo?: string | null;
};

export function CashAccountsPanel({ rows }: { rows: CashAccount[] }) {
  if (!rows.length) {
    return (
      <div className="rounded-2xl border border-dashed border-line bg-surface px-4 py-6 text-center text-sm text-muted">
        표시할 현금 잔고가 없습니다.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-surface">
      {rows.map((a) => (
        <div
          key={a.id}
          className="flex items-center justify-between gap-3 border-b border-line px-4 py-3.5 last:border-b-0"
        >
          <div className="min-w-0">
            <div className="truncate text-[15px] font-extrabold tracking-tight">
              {a.institution}
            </div>
            <div className="text-xs text-muted">
              {accountProductCode(a.memo)
                ? `${accountSubLabel(a)} · `
                : ""}
              {a.account_type} · {OWNERSHIP_KO[a.ownership] || a.ownership} ·{" "}
              {a.currency}
            </div>
          </div>
          <div className="shrink-0 text-right text-[15px] font-extrabold tracking-tight">
            {a.currency === "USD"
              ? `$${a.cash_balance.toLocaleString("en-US", {
                  maximumFractionDigits: 2,
                })}`
              : fmtKrw(a.cash_balance)}
          </div>
        </div>
      ))}
    </div>
  );
}
