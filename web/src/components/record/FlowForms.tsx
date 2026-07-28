"use client";

import { createTrade, createDividend, createCashFlow } from "@/lib/actions/record";
import {
  EXPENSE_CATEGORIES,
  INCOME_CATEGORIES,
} from "@/lib/record";
import { ActionForm, Field, Panel, inputClass } from "@/components/record/FormUI";

type Account = { id: string; institution: string | null; currency?: string | null };

function today() {
  return new Date().toISOString().slice(0, 10);
}

export function FlowForms({ accounts }: { accounts: Account[] }) {
  return (
    <div className="space-y-4">
      <Panel title="매매">
        {!accounts.length ? (
          <p className="text-sm text-muted">먼저 계좌를 만드세요.</p>
        ) : (
          <ActionForm action={createTrade} submitLabel="매매 기록">
            <Field label="계좌">
              <select name="account_id" required className={inputClass}>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.institution || "계좌"}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="구분">
              <select name="trade_type" className={inputClass} defaultValue="buy">
                <option value="buy">매수</option>
                <option value="sell">매도</option>
              </select>
            </Field>
            <Field label="티커">
              <input name="ticker" required className={inputClass} placeholder="AAPL / 005930" />
            </Field>
            <Field label="일자">
              <input name="trade_date" type="date" required defaultValue={today()} className={inputClass} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="수량">
                <input name="quantity" type="number" min={0} step="any" required className={inputClass} />
              </Field>
              <Field label="단가">
                <input name="price" type="number" min={0} step="any" required className={inputClass} />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="수수료">
                <input name="fee" type="number" min={0} step="any" defaultValue={0} className={inputClass} />
              </Field>
              <Field label="통화">
                <select name="currency" className={inputClass} defaultValue="KRW">
                  <option value="KRW">KRW</option>
                  <option value="USD">USD</option>
                </select>
              </Field>
            </div>
            <Field label="메모">
              <input name="reason" className={inputClass} />
            </Field>
          </ActionForm>
        )}
      </Panel>

      <Panel title="배당">
        <ActionForm action={createDividend} submitLabel="배당 기록">
          <Field label="계좌 (선택)">
            <select name="account_id" className={inputClass} defaultValue="">
              <option value="">없음</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.institution || "계좌"}
                </option>
              ))}
            </select>
          </Field>
          <Field label="티커">
            <input name="ticker" required className={inputClass} />
          </Field>
          <Field label="종목명">
            <input name="name" className={inputClass} placeholder="선택" />
          </Field>
          <Field label="지급일">
            <input name="pay_date" type="date" required defaultValue={today()} className={inputClass} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="금액">
              <input name="amount" type="number" min={0} step="any" required className={inputClass} />
            </Field>
            <Field label="통화">
              <select name="currency" className={inputClass} defaultValue="KRW">
                <option value="KRW">KRW</option>
                <option value="USD">USD</option>
              </select>
            </Field>
          </div>
          <Field label="메모">
            <input name="memo" className={inputClass} />
          </Field>
        </ActionForm>
      </Panel>

      <Panel title="현금흐름">
        <ActionForm action={createCashFlow} submitLabel="현금 기록">
          <Field label="유형">
            <select name="flow_type" className={inputClass} defaultValue="expense">
              <option value="income">수입</option>
              <option value="expense">지출</option>
            </select>
          </Field>
          <Field label="카테고리">
            <input
              name="category"
              required
              list="cash-cats"
              className={inputClass}
              placeholder="생활비 / 월급 등"
            />
            <datalist id="cash-cats">
              {[...INCOME_CATEGORIES, ...EXPENSE_CATEGORIES].map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
          </Field>
          <Field label="금액">
            <input name="amount" type="number" min={0} step="any" required className={inputClass} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="통화">
              <select name="currency" className={inputClass} defaultValue="KRW">
                <option value="KRW">KRW</option>
                <option value="USD">USD</option>
              </select>
            </Field>
            <Field label="일자">
              <input name="flow_date" type="date" required defaultValue={today()} className={inputClass} />
            </Field>
          </div>
          <Field label="연결 계좌 (선택)">
            <select name="account_id" className={inputClass} defaultValue="">
              <option value="">없음</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.institution || "계좌"}
                </option>
              ))}
            </select>
          </Field>
          <Field label="메모">
            <input name="memo" className={inputClass} />
          </Field>
        </ActionForm>
      </Panel>
    </div>
  );
}
