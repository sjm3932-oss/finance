"use client";

import { upsertTaxRecord } from "@/lib/actions/watchTax";
import { ActionForm, Field, Panel, inputClass } from "@/components/record/FormUI";
import { fmtKrw } from "@/lib/money";

type TaxRow = {
  tax_year: number;
  taxable_gain?: number | null;
  estimated_tax?: number | null;
  cum_capital_gain?: number | null;
  tax_threshold?: number | null;
  dividend_tax?: number | null;
} | null;

export function TaxForms({
  year,
  row,
}: {
  year: number;
  row: TaxRow;
}) {
  const cum = Number(row?.cum_capital_gain || 0);
  const threshold = Number(row?.tax_threshold ?? 2_500_000);
  const divTax = Number(row?.dividend_tax || 0);
  const taxable = Math.max(0, cum - threshold);
  const estimated = taxable * 0.22;

  return (
    <div className="space-y-4">
      <Panel title="세금 기록 저장">
        <p className="mb-3 text-xs text-muted">
          해외주식 양도소득세 추정(기본공제 · 22%). 같은 연도는 덮어씁니다.
        </p>
        <ActionForm action={upsertTaxRecord} submitLabel="저장">
          <Field label="세무연도">
            <input
              name="tax_year"
              type="number"
              min={2020}
              max={2100}
              defaultValue={year}
              required
              className={inputClass}
            />
          </Field>
          <Field label="누적 양도차익 (원)">
            <input
              name="cum_capital_gain"
              type="number"
              min={0}
              step={10000}
              defaultValue={cum}
              required
              className={inputClass}
            />
          </Field>
          <Field label="기본공제 (원)">
            <input
              name="tax_threshold"
              type="number"
              min={0}
              step={10000}
              defaultValue={threshold}
              required
              className={inputClass}
            />
          </Field>
          <Field label="배당세 (원)">
            <input
              name="dividend_tax"
              type="number"
              min={0}
              step={1000}
              defaultValue={divTax}
              required
              className={inputClass}
            />
          </Field>
        </ActionForm>
      </Panel>

      <Panel title={`${year}년 추정`}>
        <div className="space-y-2 text-sm">
          {(
            [
              ["과세대상 양도차익", row?.taxable_gain ?? taxable],
              ["예상 세금 (22%)", row?.estimated_tax ?? estimated],
              ["누적 양도차익", row?.cum_capital_gain ?? cum],
              ["기본공제", row?.tax_threshold ?? threshold],
              ["배당세", row?.dividend_tax ?? divTax],
            ] as const
          ).map(([label, v]) => (
            <div key={label} className="flex justify-between">
              <span className="font-semibold text-muted">{label}</span>
              <span className="font-extrabold">{fmtKrw(v)}</span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[11px] text-muted">
          공식: max(누적양도차익 − 기본공제, 0) × 0.22
        </p>
      </Panel>
    </div>
  );
}
