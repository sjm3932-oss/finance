"use client";

import { useMemo, useState } from "react";
import {
  createDebt,
  changeDebtRate,
  recordDebtPayment,
  adjustDebt,
} from "@/lib/actions/record";
import { DEBT_KIND_OPTIONS, OWNERSHIP_OPTIONS } from "@/lib/record";
import { todayKst } from "@/lib/dates";
import { ActionForm, Field, Panel, inputClass } from "@/components/record/FormUI";
import { fmtKrw } from "@/lib/money";

type Debt = {
  id?: string;
  lender: string | null;
  principal: number | null;
  interest_rate?: number | null;
};

type Account = { id: string; institution: string | null };

type ActionTab = "pay" | "rate" | "adjust";

function today() {
  return todayKst();
}

export function DebtForms({
  debts,
  accounts,
}: {
  debts: Debt[];
  accounts: Account[];
}) {
  const withId = debts.filter((d) => d.id) as (Debt & { id: string })[];
  const [debtId, setDebtId] = useState(withId[0]?.id ?? "");
  const [action, setAction] = useState<ActionTab>("pay");

  const selected = useMemo(
    () => withId.find((d) => d.id === debtId) ?? withId[0] ?? null,
    [withId, debtId]
  );

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
            <input
              name="principal"
              type="number"
              min={0}
              step={100000}
              required
              className={inputClass}
            />
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
          <div className="grid grid-cols-2 gap-3">
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
          </div>
          <Field label="소유">
            <select name="ownership" className={inputClass} defaultValue="joint">
              {OWNERSHIP_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
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

      {selected ? (
        <Panel title="부채 관리">
          <Field label="부채">
            <select
              className={inputClass}
              value={selected.id}
              onChange={(e) => setDebtId(e.target.value)}
            >
              {withId.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.lender} · {fmtKrw(d.principal)}
                  {d.interest_rate != null ? ` · ${d.interest_rate}%` : ""}
                </option>
              ))}
            </select>
          </Field>

          <div className="mt-3 flex flex-wrap gap-1.5">
            {(
              [
                ["pay", "월 납부"],
                ["rate", "이자율"],
                ["adjust", "차입·상환"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setAction(id)}
                className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                  action === id
                    ? "bg-brand text-white"
                    : "bg-canvas text-muted ring-1 ring-line"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="mt-4">
            {action === "pay" ? (
              <ActionForm
                key={`pay-${selected.id}`}
                action={recordDebtPayment}
                submitLabel="납부 기록"
              >
                <input type="hidden" name="debt_id" value={selected.id} />
                <Field label="납부 금액">
                  <input
                    name="amount"
                    type="number"
                    min={0}
                    step={10000}
                    required
                    className={inputClass}
                  />
                </Field>
                <Field label="납부일">
                  <input
                    name="tx_date"
                    type="date"
                    defaultValue={today()}
                    className={inputClass}
                  />
                </Field>
                <Field label="메모">
                  <input
                    name="memo"
                    className={inputClass}
                    defaultValue="월 원리금 납부"
                  />
                </Field>
              </ActionForm>
            ) : null}

            {action === "rate" ? (
              <ActionForm
                key={`rate-${selected.id}`}
                action={changeDebtRate}
                submitLabel="이자율 저장"
              >
                <input type="hidden" name="debt_id" value={selected.id} />
                <Field label="새 연 이자율(%)">
                  <input
                    name="interest_rate"
                    type="number"
                    min={0}
                    step={0.1}
                    required
                    defaultValue={Number(selected.interest_rate || 0)}
                    className={inputClass}
                  />
                </Field>
                <Field label="적용일">
                  <input
                    name="effective_date"
                    type="date"
                    defaultValue={today()}
                    className={inputClass}
                  />
                </Field>
                <Field label="사유">
                  <input name="memo" className={inputClass} />
                </Field>
              </ActionForm>
            ) : null}

            {action === "adjust" ? (
              <ActionForm
                key={`adj-${selected.id}`}
                action={adjustDebt}
                submitLabel="기록"
              >
                <input type="hidden" name="debt_id" value={selected.id} />
                <Field label="유형">
                  <select
                    name="tx_type"
                    className={inputClass}
                    defaultValue="repayment"
                  >
                    <option value="repayment">원금 상환</option>
                    <option value="increase">추가 차입</option>
                  </select>
                </Field>
                <Field label="금액">
                  <input
                    name="amount"
                    type="number"
                    min={0}
                    step={10000}
                    required
                    className={inputClass}
                  />
                </Field>
                <Field label="일자">
                  <input
                    name="tx_date"
                    type="date"
                    defaultValue={today()}
                    className={inputClass}
                  />
                </Field>
                <Field label="메모">
                  <input name="memo" className={inputClass} />
                </Field>
              </ActionForm>
            ) : null}
          </div>
        </Panel>
      ) : null}
    </div>
  );
}
