"use client";

import { useMemo, useState } from "react";
import { DEPOSIT_KIND_OPTIONS } from "@/lib/record";
import { Field, inputClass } from "@/components/record/FormUI";
import { fmtKrw } from "@/lib/money";
import {
  installmentProgress,
  isMonthlyDeposit,
  type DepositRow,
} from "@/lib/portfolio";

export function DepositKindFields({ deposit }: { deposit?: DepositRow }) {
  const [kind, setKind] = useState(deposit?.deposit_kind || "time");
  const [monthly, setMonthly] = useState(
    Number(deposit?.monthly_amount || 0) > 0
      ? String(Number(deposit?.monthly_amount))
      : ""
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
      }),
    [kind, monthly, rate, start, maturity]
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
          <input type="hidden" name="current_value" value={0} />
          <Field label="월 납입액(원)">
            <input
              name="monthly_amount"
              type="number"
              min={0}
              step={10000}
              required
              className={inputClass}
              value={monthly}
              onChange={(e) => setMonthly(e.target.value)}
              placeholder="매월 넣는 금액"
            />
          </Field>
        </>
      ) : (
        <>
          <input type="hidden" name="monthly_amount" value={0} />
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
            required={monthlyKind}
            className={inputClass}
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </Field>
        <Field label="만기일">
          <input
            name="maturity_date"
            type="date"
            required={monthlyKind}
            className={inputClass}
            value={maturity}
            onChange={(e) => setMaturity(e.target.value)}
          />
        </Field>
      </div>
      {prog ? (
        <div className="rounded-xl bg-canvas px-3 py-2.5 text-xs font-semibold text-muted">
          {prog.paymentsMade}/{prog.paymentsTotal}회 납입 · 누적원금{" "}
          {fmtKrw(prog.principal)}
          {prog.interest > 0 ? ` · 경과이자 ${fmtKrw(prog.interest)}` : ""}
          {" → 오늘 "}
          <span className="text-ink">{fmtKrw(prog.value)}</span>
          {prog.maturityValue > 0 ? (
            <>
              {" · 만기약 "}
              {fmtKrw(prog.maturityValue)}
              {prog.maturityInterest > 0
                ? ` (이자 ${fmtKrw(prog.maturityInterest)})`
                : ""}
            </>
          ) : null}
        </div>
      ) : monthlyKind ? (
        <p className="text-xs text-muted">
          월 납입액·가입일·만기를 넣으면 오늘까지 낸 횟수와 단리 이자가 자동으로
          계산됩니다.
        </p>
      ) : null}
    </>
  );
}
