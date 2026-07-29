"use client";

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
import { CreateAccountFields } from "@/components/record/CreateAccountFields";
import { fmtKrw } from "@/lib/money";

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
  const withId = otherAssets.filter((o) => o.id);

  return (
    <div className="space-y-4">
      <Panel title="새 계좌 추가">
        <p className="mb-3 text-xs text-muted">
          아래 목록은 고정 메뉴가 아닙니다. 금융기관·통화는 직접 입력해 얼마든지
          추가할 수 있습니다.
        </p>
        <CreateAccountFields submitLabel="계좌 추가" />
      </Panel>

      <Panel title={`등록된 계좌 현금 · 소유 (${accounts.length})`}>
        {!accounts.length ? (
          <p className="text-sm text-muted">
            아직 등록된 계좌가 없습니다. 위에서 먼저 추가하세요.
          </p>
        ) : (
          <div className="space-y-4">
            {accounts.map((a) => (
              <div key={a.id} className="rounded-xl bg-canvas p-3">
                <p className="mb-2 text-sm font-extrabold">
                  {a.institution || "계좌"}{" "}
                  <span className="text-xs font-semibold text-muted">
                    {a.currency || "KRW"}
                  </span>
                </p>
                <ActionForm action={updateAccountCash} submitLabel="저장">
                  <input type="hidden" name="account_id" value={a.id} />
                  <Field label="현금/예수금">
                    <input
                      name="cash_balance"
                      type="number"
                      min={0}
                      step={10000}
                      defaultValue={Number(a.cash_balance || 0)}
                      className={inputClass}
                    />
                  </Field>
                  <Field label="소유">
                    <select
                      name="ownership"
                      className={inputClass}
                      defaultValue={a.ownership || "joint"}
                    >
                      {OWNERSHIP_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </Field>
                </ActionForm>
              </div>
            ))}
          </div>
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

      {withId.length ? (
        <Panel title="기타자산 수정 · 삭제">
          <ActionForm action={updateOtherAssetValue} submitLabel="평가액 저장">
            <Field label="항목">
              <select name="id" required className={inputClass} defaultValue={withId[0].id}>
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
                defaultValue={Number(withId[0].value_krw || 0)}
                className={inputClass}
              />
            </Field>
          </ActionForm>
          <div className="mt-3 border-t border-line pt-3">
            <ActionForm action={deleteOtherAsset} submitLabel="선택 항목 삭제">
              <Field label="삭제할 항목">
                <select name="id" required className={inputClass} defaultValue={withId[0].id}>
                  {withId.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.name}
                    </option>
                  ))}
                </select>
              </Field>
            </ActionForm>
          </div>
        </Panel>
      ) : null}
    </div>
  );
}
