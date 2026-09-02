"use client";

import { createAccount } from "@/lib/actions/record";
import { ACCOUNT_TYPE_OPTIONS, OWNERSHIP_OPTIONS } from "@/lib/record";
import { ActionForm, Field, inputClass } from "@/components/record/FormUI";

/** Free-form account create: any institution name + any ISO currency code. */
export function CreateAccountFields({
  submitLabel = "계좌 추가",
}: {
  submitLabel?: string;
}) {
  return (
    <ActionForm action={createAccount} submitLabel={submitLabel}>
      <Field label="금융기관 (자유 입력)">
        <input
          name="institution"
          required
          className={inputClass}
          placeholder="예: 한국투자, 신한은행, IBKR…"
          autoComplete="off"
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="계좌유형">
          <select name="account_type" className={inputClass} defaultValue="brokerage">
            {ACCOUNT_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="통화 (자유 입력)">
          <input
            name="currency"
            required
            className={inputClass}
            defaultValue="KRW"
            placeholder="KRW / USD / EUR…"
            list="currency-suggestions"
            autoComplete="off"
          />
          <datalist id="currency-suggestions">
            <option value="KRW" />
            <option value="USD" />
            <option value="EUR" />
            <option value="JPY" />
          </datalist>
        </Field>
      </div>
      <Field label="소유">
        <select name="ownership" className={inputClass} defaultValue="mine">
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
          placeholder="예: ISA, 계좌 끝자리 1234"
        />
      </Field>
    </ActionForm>
  );
}
