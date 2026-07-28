import Link from "next/link";
import { loadDebtDashboard } from "@/lib/data-insights";
import { DEBT_KIND_KO } from "@/lib/insights";
import { SimpleBarChart } from "@/components/Charts";
import { fmtKrw } from "@/lib/money";

export const dynamic = "force-dynamic";

export default async function DebtsPage() {
  const data = await loadDebtDashboard(null);

  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-bold text-muted">
          <Link href="/more" className="text-brand">
            더보기
          </Link>{" "}
          / 부채
        </p>
        <h1 className="mt-1 text-xl font-extrabold tracking-tight">부채</h1>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {(
          [
            ["총 잔금", data.total],
            ["최초 원금", data.original],
            ["누적 상환(추정)", data.repaid],
            ["건수", data.debts.length],
          ] as const
        ).map(([label, v]) => (
          <div
            key={label}
            className="rounded-2xl border border-line bg-surface px-3 py-3 shadow-soft"
          >
            <div className="text-[11px] font-semibold text-muted">{label}</div>
            <div className="mt-1 text-sm font-extrabold">
              {label === "건수" ? `${v}건` : fmtKrw(Number(v))}
            </div>
          </div>
        ))}
      </div>

      <SimpleBarChart
        title="종류별 잔금"
        bars={data.byKind.map((k) => ({
          label: DEBT_KIND_KO[k.kind] || k.kind,
          value: k.value,
        }))}
      />

      <section className="overflow-hidden rounded-2xl border border-line bg-surface">
        <div className="border-b border-line px-4 py-3 text-sm font-extrabold">
          부채 상세
        </div>
        {data.debts.map((d) => {
          const bal = Number(d.principal || 0);
          const rate = Number(d.interest_rate || 0);
          const monthlyInterest = Math.round((bal * rate) / 100 / 12);
          return (
            <div
              key={d.id || d.lender}
              className="border-b border-line px-4 py-3 last:border-b-0"
            >
              <div className="flex justify-between gap-3">
                <div>
                  <div className="text-sm font-extrabold">{d.lender}</div>
                  <div className="text-xs text-muted">
                    {DEBT_KIND_KO[d.debt_kind || ""] || d.debt_kind} · 연 {rate}%
                    {d.due_date ? ` · 만기 ${String(d.due_date).slice(0, 10)}` : ""}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-extrabold">{fmtKrw(bal)}</div>
                  <div className="text-[11px] text-muted">
                    이달 이자≈{fmtKrw(monthlyInterest)}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
        {!data.debts.length ? (
          <p className="px-4 py-8 text-center text-sm text-muted">
            등록된 부채가 없습니다.
          </p>
        ) : null}
      </section>

      <p className="text-xs text-muted">
        납부·등록은{" "}
        <Link href="/record?tab=debt" className="font-semibold text-brand">
          기록 → 부채
        </Link>
      </p>
    </div>
  );
}
