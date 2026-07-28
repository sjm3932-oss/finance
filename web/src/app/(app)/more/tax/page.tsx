import Link from "next/link";
import { loadTaxYear } from "@/lib/data-insights";
import { fmtKrw } from "@/lib/money";

export const dynamic = "force-dynamic";

export default async function TaxPage() {
  const { year, row } = await loadTaxYear();

  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-bold text-muted">
          <Link href="/more" className="text-brand">
            더보기
          </Link>{" "}
          / 세금
        </p>
        <h1 className="mt-1 text-xl font-extrabold tracking-tight">세금</h1>
        <p className="mt-1 text-sm text-muted">{year}년 추정</p>
      </div>

      {!row ? (
        <div className="rounded-2xl border border-dashed border-line bg-surface px-4 py-10 text-center text-sm text-muted">
          세금 기록이 없습니다. Streamlit에서 tax_records를 입력하세요.
        </div>
      ) : (
        <div className="space-y-3 rounded-2xl border border-line bg-surface p-4 shadow-soft">
          {(
            [
              ["과세대상 양도차익", row.taxable_gain],
              ["예상 세금 (22%)", row.estimated_tax],
              ["누적 양도차익", row.cum_capital_gain],
              ["기본공제", row.tax_threshold],
              ["배당세", row.dividend_tax],
            ] as const
          ).map(([label, v]) => (
            <div key={label} className="flex justify-between text-sm">
              <span className="font-semibold text-muted">{label}</span>
              <span className="font-extrabold">{fmtKrw(v as number | null)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
