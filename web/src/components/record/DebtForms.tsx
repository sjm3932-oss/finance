"use client";

import {
  createDebt,
  changeDebtRate,
  recordDebtPayment,
  adjustDebt,
} from "@/lib/actions/record";
import { DEBT_KIND_OPTIONS } from "@/lib/record";
import { ActionForm, Field, Panel, inputClass } from "@/components/record/FormUI";
import { fmtKrw } from "@/lib/money";

type Debt = {
  id?: string;
  lender: string | null;
  principal: number | null;
  interest_rate?: number | null;
};

type Account = { id: string; institution: string | null };

function today() {
  return new Date().toISOString().slice(0, 10);
}

export function DebtForms({
  debts,
  accounts,
}: {
  debts: Debt[];
  accounts: Account[];
}) {
  const withId = debts.filter((d) => d.id);

  return (
    <div className="space-y-4">
      <Panel title="부채 등록">
        <ActionForm action={createDebt} submitLabel="등록">
          <Field label="대출명/기관">
            <input name="lender" required className={inputClass} />
          </Field>
          <Field label="종류">
            <select name="debt_kind" className={inputClass} defaultValue="mortgage">
              {DEBT_KIND_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="현재 잔금(원)">
            <input name="principal" type="number" min={0} step={100000} required className={inputClass} />
          </Field>
          <Field label="최초 원금(원)">
            <input
              name="original_principal"
              type="number"
              min={0}
              step={100000}
              defaultValue={0}
              className={inputClass}
            />
          </Field>
          <Field label="연 이자율(%)">
            <input
              name="interest_rate"
              type="number"
              min={0}
              step={0.1}
              defaultValue={3.5}
              className={inputClass}
            />
          </Field>
          <Field label="만기일">
            <input name="due_date" type="date" className={inputClass} />
          </Field>
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

      {withId.length ? (
        <>
          <Panel title="월 납부">
            <ActionForm action={recordDebtPayment} submitLabel="납부 기록">
              <Field label="부채">
                <select name="debt_id" required className={inputClass}>
                  {withId.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.lender} ({fmtKrw(d.principal)})
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="납부 금액">
                <input name="amount" type="number" min={0} step={10000} required className={inputClass} />
              </Field>
              <Field label="납부일">
                <input name="tx_date" type="date" defaultValue={today()} className={inputClass} />
              </Field>
              <Field label="메모">
                <input name="memo" className={inputClass} defaultValue="월 원리금 납부" />
              </Field>
            </ActionForm>
          </Panel>

          <Panel title="이자율 변경">
            <ActionForm action={changeDebtRate} submitLabel="이자율 저장">
              <Field label="부채">
                <select name="debt_id" required className={inputClass}>
                  {withId.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.lender} ({d.interest_rate ?? "—"}%)
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="새 연 이자율(%)">
                <input name="interest_rate" type="number" min={0} step={0.1} required className={inputClass} />
              </Field>
              <Field label="적용일">
                <input name="effective_date" type="date" defaultValue={today()} className={inputClass} />
              </Field>
              <Field label="사유">
                <input name="memo" className={inputClass} />
              </Field>
            </ActionForm>
          </Panel>

          <Panel title="추가차입 · 원금상환">
            <ActionForm action={adjustDebt} submitLabel="기록">
              <Field label="부채">
                <select name="debt_id" required className={inputClass}>
                  {withId.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.lender}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="유형">
                <select name="tx_type" className={inputClass} defaultValue="repayment">
                  <option value="repayment">원금 상환</option>
                  <option value="increase">추가 차입</option>
                </select>
              </Field>
              <Field label="금액">
                <input name="amount" type="number" min={0} step={10000} required className={inputClass} />
              </Field>
              <Field label="일자">
                <input name="tx_date" type="date" defaultValue={today()} className={inputClass} />
              </Field>
              <Field label="메모">
                <input name="memo" className={inputClass} />
              </Field>
            </ActionForm>
          </Panel>
        </>
      ) : null}
    </div>
  );
}
