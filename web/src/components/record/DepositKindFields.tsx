"use client";

import { useMemo, useState } from "react";
import { DEPOSIT_KIND_OPTIONS } from "@/lib/record";
import { Field, inputClass } from "@/components/record/FormUI";
import { fmtKrw } from "@/lib/money";
import { todayKst } from "@/lib/dates";
import {
  installmentProgress,
  isMonthlyDeposit,
  type DepositRow,
} from "@/lib/portfolio";

export function DepositKindFields({ deposit }: { deposit?: DepositRow }) {
  const [kind, setKind] = useState(deposit?.deposit_kind || "time");
  const [monthly, setMonthly] = useState(() => {
    if (deposit && isMonthlyDeposit(deposit.deposit_kind)) {
      return String(Number(deposit.monthly_amount || 0));
    }
    const n = Number(deposit?.monthly_amount || 0);
    return n > 0 ? String(n) : "";
  });
  const [current, setCurrent] = useState(
    Number(deposit?.current_value || 0) > 0
      ? String(Number(deposit?.current_value))
      : ""
  );
  const [balanceAsOf, setBalanceAsOf] = useState(
    deposit?.balance_as_of ? String(deposit.balance_as_of).slice(0, 10) : ""
  );
  const [rate, setRate] = useState(String(Number(deposit?.interest_rate || 0)));
  const [start, setStart] = useState(
    deposit?.start_date ? String(deposit.start_date).slice(0, 10) : ""
  );
  const [maturity, setMaturity] = useState(
    deposit?.maturity_date ? String(deposit.maturity_date).slice(0, 10) : ""
  );
  const monthlyKind = isMonthlyDeposit(kind);
  const prog = useMemo(
    () =>
      installmentProgress({
        deposit_kind: kind,
        monthly_amount: Number(monthly) || 0,
        interest_rate: Number(rate) || 0,
        start_date: start || null,
        maturity_date: maturity || null,
        current_value: Number(current) || 0,
        balance_as_of: balanceAsOf || (Number(current) > 0 ? todayKst() : null),
      }),
    [kind, monthly, rate, start, maturity, current, balanceAsOf]
  );

  return (
    <>
      <Field label="종류">
        <select
          name="deposit_kind"
          className={inputClass}
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          {DEPOSIT_KIND_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </Field>
      {monthlyKind ? (
        <>
          <input type="hidden" name="principal" value={0} />
          <Field label="월 납입액(원)">
            <input
              name="monthly_amount"
              type="number"
              min={0}
              step={10000}
              className={inputClass}
              value={monthly}
              onChange={(e) => setMonthly(e.target.value)}
              placeholder="납입 중단이면 0"
            />
          </Field>
          <p className="text-xs text-muted">
            이미 넣고 있는 적금·청약은 <span className="text-ink">실제 가입일</span>을
            넣으면 지금까지 회차가 자동으로 잡힙니다. 은행 잔액이 다르면 아래{" "}
            <span className="text-ink">현재 잔액</span>을 넣으세요. 납입을 그만둔 상품은
            월 납입액 0과 현재 잔액만 넣으면 됩니다.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <Field label="현재 잔액(원, 선택)">
              <input
                name="current_value"
                type="number"
                min={0}
                step={10000}
                required={monthly === "0"}
                className={inputClass}
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                placeholder="비우면 가입일부터 자동"
              />
            </Field>
            <Field label="잔액 기준일">
              <input
                name="balance_as_of"
                type="date"
                className={inputClass}
                value={balanceAsOf}
                onChange={(e) => setBalanceAsOf(e.target.value)}
                disabled={!current}
              />
            </Field>
          </div>
        </>
      ) : (
        <>
          <input type="hidden" name="monthly_amount" value={0} />
          <input type="hidden" name="balance_as_of" value="" />
          <div className="grid grid-cols-2 gap-3">
            <Field label="원금(원)">
              <input
                name="principal"
                type="number"
                min={0}
                step={100000}
                required
                className={inputClass}
                defaultValue={Number(deposit?.principal || 0) || undefined}
              />
            </Field>
            <Field label="현재 잔액(원)">
              <input
                name="current_value"
                type="number"
                min={0}
                step={100000}
                className={inputClass}
                defaultValue={
                  Number(deposit?.current_value || deposit?.principal || 0) ||
                  undefined
                }
                placeholder="비우면 원금과 동일"
              />
            </Field>
          </div>
        </>
      )}
      <Field label="연 이자율(%)">
        <input
          name="interest_rate"
          type="number"
          min={0}
          step={0.01}
          className={inputClass}
          value={rate}
          onChange={(e) => setRate(e.target.value)}
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label={monthlyKind ? "가입일 (첫 납입)" : "가입일"}>
          <input
            name="start_date"
            type="date"
            required={monthlyKind && Number(monthly || 0) > 0}
            className={inputClass}
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </Field>
        <Field label="만기일">
          <input
            name="maturity_date"
            type="date"
            required={monthlyKind && Number(monthly || 0) > 0}
            className={inputClass}
            value={maturity}
            onChange={(e) => setMaturity(e.target.value)}
          />
        </Field>
      </div>
      {prog ? (
        <div className="rounded-xl bg-canvas px-3 py-2.5 text-xs font-semibold text-muted">
          {prog.paymentsMade}/{prog.paymentsTotal}회
          {prog.seeded
            ? ` · 은행잔액 ${fmtKrw(prog.seedValue)}${
                prog.extraPayments > 0
                  ? ` + 이후 ${prog.extraPayments}회`
                  : ""
              }`
            : ` · 누적원금 ${fmtKrw(prog.principal)}`}
          {prog.interest > 0 && !prog.seeded
            ? ` · 경과이자 ${fmtKrw(prog.interest)}`
            : ""}
          {" → 오늘 "}
          <span className="text-ink">{fmtKrw(prog.value)}</span>
          {prog.maturityValue > 0 ? (
            <>
              {" · 만기약 "}
              {fmtKrw(prog.maturityValue)}
            </>
          ) : null}
        </div>
      ) : monthlyKind && Number(current) > 0 && Number(monthly || 0) === 0 ? (
        <p className="text-xs font-semibold text-muted">
          납입 중단 · 오늘 잔액{" "}
          <span className="text-ink">{fmtKrw(Number(current))}</span>
        </p>
      ) : monthlyKind ? (
        <p className="text-xs text-muted">
          월 납입액·가입일·만기를 넣으면 오늘까지 낸 횟수가 자동으로 계산됩니다.
          납입을 그만둔 상품은 월 납입액 0과 현재 잔액을 넣으세요.
        </p>
      ) : null}
    </>
  );
}
