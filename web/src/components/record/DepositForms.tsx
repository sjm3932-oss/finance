"use client";

import { createDeposit } from "@/lib/actions/record";
import { OWNERSHIP_OPTIONS } from "@/lib/record";
import { ActionForm, Field, Panel, inputClass } from "@/components/record/FormUI";
import { DepositEditRow } from "@/components/record/DepositEditRow";
import { DepositKindFields } from "@/components/record/DepositKindFields";
import type { DepositRow } from "@/lib/portfolio";
import { depositBalance } from "@/lib/portfolio";
import { fmtKrw } from "@/lib/money";
import Link from "next/link";

export function DepositForms({ deposits }: { deposits: DepositRow[] }) {
  const withId = deposits.filter(
    (d): d is DepositRow & { id: string } => Boolean(d.id)
  );
  const total = withId.reduce((s, d) => s + depositBalance(d), 0);

  return (
    <div className="space-y-4">
      <Panel title="예적금 추가">
        <p className="mb-3 text-xs text-muted">
          적금·청약은 월 납입액만 넣으면 매달 자동으로 원금이 쌓입니다.
          증권 예수금은 토스·한투 동기화, 부동산·연금은{" "}
          <Link href="/record?tab=wealth" className="font-semibold text-brand">
            부동산·기타
          </Link>
          .
        </p>
        <ActionForm action={createDeposit} submitLabel="추가">
          <div className="grid grid-cols-2 gap-3">
            <Field label="금융기관">
              <input
                name="institution"
                required
                className={inputClass}
                placeholder="예: 신한은행"
                autoComplete="off"
              />
            </Field>
            <Field label="상품 이름">
              <input
                name="name"
                required
                className={inputClass}
                placeholder="예: 1년 적금"
                autoComplete="off"
              />
            </Field>
          </div>
          <DepositKindFields />
          <Field label="소유">
            <select name="ownership" className={inputClass} defaultValue="joint">
              {OWNERSHIP_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="메모">
            <input
              name="memo"
              className={inputClass}
              placeholder="예: 자동이체, 비과세"
            />
          </Field>
        </ActionForm>
      </Panel>

      <Panel title={`등록된 예적금 (${withId.length}) · ${fmtKrw(total)}`}>
        {!withId.length ? (
          <p className="text-sm text-muted">아직 예적금이 없습니다.</p>
        ) : (
          <ul className="divide-y divide-line">
            {withId.map((row) => (
              <DepositEditRow key={row.id} deposit={row} />
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
