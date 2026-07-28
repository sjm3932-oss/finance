import Link from "next/link";
import { loadTaxYear } from "@/lib/data-insights";
import { TaxForms } from "@/components/TaxForms";

export const dynamic = "force-dynamic";

export default async function TaxPage({
  searchParams,
}: {
  searchParams: Promise<{ year?: string }>;
}) {
  const sp = await searchParams;
  const yearNum = Number(sp.year);
  const year = Number.isFinite(yearNum) && yearNum >= 2020 ? yearNum : undefined;
  const { year: y, row } = await loadTaxYear(year);

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
        <p className="mt-1 text-sm text-muted">{y}년 기록 · 추정</p>
      </div>
      <TaxForms year={y} row={row} />
    </div>
  );
}
