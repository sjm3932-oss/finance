"use client";

import { useMemo, useState } from "react";
import {
  createOtherAsset,
  updateOtherAssetValue,
  deleteOtherAsset,
  updateAccountCash,
} from "@/lib/actions/record";
import {
  ASSET_KIND_OPTIONS,
  OWNERSHIP_OPTIONS,
} from "@/lib/record";
import { ActionForm, Field, Panel, inputClass } from "@/components/record/FormUI";
import { fmtKrw } from "@/lib/money";
import Link from "next/link";

type OtherAsset = {
  id?: string;
  name: string | null;
  asset_kind: string | null;
  value_krw: number | null;
  ownership: string | null;
};

type Account = {
  id: string;
  institution: string | null;
  ownership?: string | null;
  cash_balance?: number | null;
  currency?: string | null;
};

export function WealthForms({
  otherAssets,
  accounts,
}: {
  otherAssets: OtherAsset[];
  accounts: Account[];
}) {
  const withId = otherAssets.filter((o) => o.id) as (OtherAsset & { id: string })[];
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? "");
  const [otherId, setOtherId] = useState(withId[0]?.id ?? "");

  const selectedAccount = useMemo(
    () => accounts.find((a) => a.id === accountId) ?? accounts[0] ?? null,
    [accounts, accountId]
  );
  const selectedOther = useMemo(
    () => withId.find((o) => o.id === otherId) ?? withId[0] ?? null,
    [withId, otherId]
  );

  return (
    <div className="space-y-4">
      <Panel title="계좌 현금 · 소유">
        {!accounts.length || !selectedAccount ? (
          <p className="text-sm text-muted">
            등록된 계좌가 없습니다.{" "}
            <Link href="/record?tab=account" className="font-semibold text-brand">
              계좌 탭
            </Link>
            에서 먼저 추가하세요.
          </p>
        ) : (
          <ActionForm
            key={selectedAccount.id}
            action={updateAccountCash}
            submitLabel="저장"
          >
            <input type="hidden" name="account_id" value={selectedAccount.id} />
            <Field label="계좌">
              <select
                className={inputClass}
                value={selectedAccount.id}
                onChange={(e) => setAccountId(e.target.value)}
              >
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.institution || "계좌"} · {a.currency || "KRW"}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="현금/예수금">
              <input
                name="cash_balance"
                type="number"
                min={0}
                step={10000}
                defaultValue={Number(selectedAccount.cash_balance || 0)}
                className={inputClass}
              />
            </Field>
            <Field label="소유">
              <select
                name="ownership"
                className={inputClass}
                defaultValue={selectedAccount.ownership || "joint"}
              >
                {OWNERSHIP_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </Field>
          </ActionForm>
        )}
      </Panel>

      <Panel title="기타자산 추가">
        <ActionForm action={createOtherAsset} submitLabel="추가">
          <Field label="이름">
            <input name="name" required className={inputClass} placeholder="예: 아파트" />
          </Field>
          <Field label="종류">
            <select name="asset_kind" className={inputClass} defaultValue="real_estate">
              {ASSET_KIND_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="평가액(원)">
            <input
              name="value_krw"
              type="number"
              min={0}
              step={100000}
              defaultValue={0}
              className={inputClass}
            />
          </Field>
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
            <input name="memo" className={inputClass} placeholder="선택" />
          </Field>
        </ActionForm>
      </Panel>

      {withId.length && selectedOther ? (
        <Panel title="기타자산 수정 · 삭제">
          <ActionForm
            key={`upd-${selectedOther.id}`}
            action={updateOtherAssetValue}
            submitLabel="평가액 저장"
          >
            <Field label="항목">
              <select
                name="id"
                required
                className={inputClass}
                value={selectedOther.id}
                onChange={(e) => setOtherId(e.target.value)}
              >
                {withId.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name} ({fmtKrw(o.value_krw)})
                  </option>
                ))}
              </select>
            </Field>
            <Field label="평가액(원)">
              <input
                name="value_krw"
                type="number"
                min={0}
                step={100000}
                defaultValue={Number(selectedOther.value_krw || 0)}
                className={inputClass}
              />
            </Field>
          </ActionForm>
          <div className="mt-3 border-t border-line pt-3">
            <ActionForm
              key={`del-${selectedOther.id}`}
              action={deleteOtherAsset}
              submitLabel="선택 항목 삭제"
            >
              <input type="hidden" name="id" value={selectedOther.id} />
              <p className="text-sm text-muted">
                위에서 고른 「{selectedOther.name}」을(를) 삭제합니다.
              </p>
            </ActionForm>
          </div>
        </Panel>
      ) : null}
    </div>
  );
}
