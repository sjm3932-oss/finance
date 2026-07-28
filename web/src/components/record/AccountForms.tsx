"use client";

import { createAccount } from "@/lib/actions/record";
import { ACCOUNT_TYPE_OPTIONS } from "@/lib/record";
import { ActionForm, Field, Panel, inputClass } from "@/components/record/FormUI";

type Account = {
  id: string;
  institution: string | null;
  account_type: string | null;
  currency: string | null;
};

export function AccountForms({ accounts }: { accounts: Account[] }) {
  return (
    <div className="space-y-4">
      <Panel title="계좌 만들기">
        <ActionForm action={createAccount} submitLabel="계좌 추가">
          <Field label="금융기관">
            <input name="institution" required className={inputClass} placeholder="예: 한국투자" />
          </Field>
          <Field label="계좌유형">
            <select name="account_type" className={inputClass} defaultValue="brokerage">
              {ACCOUNT_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="통화">
            <select name="currency" className={inputClass} defaultValue="KRW">
              <option value="KRW">KRW</option>
              <option value="USD">USD</option>
            </select>
          </Field>
        </ActionForm>
      </Panel>

      <Panel title="등록된 계좌">
        {!accounts.length ? (
          <p className="text-sm text-muted">아직 계좌가 없습니다.</p>
        ) : (
          <ul className="divide-y divide-line">
            {accounts.map((a) => (
              <li key={a.id} className="flex items-center justify-between py-2.5 text-sm">
                <span className="font-extrabold tracking-tight">
                  {a.institution || "계좌"}
                </span>
                <span className="text-xs font-semibold text-muted">
                  {a.account_type} · {a.currency}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
