"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { deleteDeposit, updateDeposit } from "@/lib/actions/record";
import { OWNERSHIP_OPTIONS } from "@/lib/record";
import { ActionForm, Field, inputClass } from "@/components/record/FormUI";
import { DepositKindFields } from "@/components/record/DepositKindFields";
import { fmtKrw } from "@/lib/money";
import {
  DEPOSIT_KIND_KO,
  OWNERSHIP_KO,
  depositBalance,
  depositExpectedInterest,
  installmentProgress,
  type DepositRow,
} from "@/lib/portfolio";

export function DepositEditRow({ deposit }: { deposit: DepositRow & { id: string } }) {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const [delMsg, setDelMsg] = useState<string | null>(null);
  const [deleting, startDelete] = useTransition();

  const kindLabel =
    DEPOSIT_KIND_KO[deposit.deposit_kind || ""] || deposit.deposit_kind || "예적금";
  const ownLabel = OWNERSHIP_KO[deposit.ownership || "joint"] || "공동";
  const balance = depositBalance(deposit);
  const expected = depositExpectedInterest(deposit);
  const prog = installmentProgress(deposit);
  const maturity = deposit.maturity_date
    ? String(deposit.maturity_date).slice(0, 10)
    : null;
  const rate = Number(deposit.interest_rate || 0);

  return (
    <li className="py-2.5">
      <div className="flex items-center justify-between gap-3 text-sm">
        <div className="min-w-0">
          <div className="font-extrabold tracking-tight">
            {deposit.name || "예적금"}
          </div>
          <div className="mt-0.5 text-xs font-semibold text-muted">
            {deposit.institution || "금융기관"} · {kindLabel} · {ownLabel}
            {rate > 0 ? ` · 연 ${rate}%` : ""}
            {prog
              ? ` · ${prog.paymentsMade}/${prog.paymentsTotal}회 · 월 ${fmtKrw(prog.monthly)}`
              : ""}
            {maturity ? ` · 만기 ${maturity}` : ""}
          </div>
          {deposit.memo ? (
            <p className="mt-1 text-xs text-muted">{deposit.memo}</p>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <div className="text-right">
            <div className="text-sm font-extrabold">{fmtKrw(balance)}</div>
            {prog ? (
              <div className="text-[11px] text-muted">
                만기≈{fmtKrw(prog.maturityValue)}
              </div>
            ) : expected != null ? (
              <div className="text-[11px] text-muted">만기이자≈{fmtKrw(expected)}</div>
            ) : null}
          </div>
          <button
            type="button"
            onClick={() => {
              setDelMsg(null);
              setOpen((v) => !v);
            }}
            className="rounded-lg px-2.5 py-1 text-xs font-extrabold text-brand ring-1 ring-line transition-transform active:scale-95"
          >
            {open ? "닫기" : "편집"}
          </button>
        </div>
      </div>

      {open ? (
        <div className="mt-3 space-y-3 rounded-xl bg-canvas px-3 py-3">
          <ActionForm
            key={[
              deposit.id,
              deposit.institution,
              deposit.name,
              deposit.deposit_kind,
              deposit.principal,
              deposit.current_value,
              deposit.monthly_amount,
              deposit.interest_rate,
              deposit.start_date,
              deposit.maturity_date,
              deposit.ownership,
              deposit.memo,
            ].join("|")}
            action={updateDeposit}
            submitLabel="저장"
          >
            <input type="hidden" name="id" value={deposit.id} />
            <div className="grid grid-cols-2 gap-3">
              <Field label="금융기관">
                <input
                  name="institution"
                  required
                  className={inputClass}
                  defaultValue={deposit.institution || ""}
                  autoComplete="off"
                />
              </Field>
              <Field label="상품 이름">
                <input
                  name="name"
                  required
                  className={inputClass}
                  defaultValue={deposit.name || ""}
                  autoComplete="off"
                />
              </Field>
            </div>
            <DepositKindFields deposit={deposit} />
            <Field label="소유">
              <select
                name="ownership"
                className={inputClass}
                defaultValue={deposit.ownership || "joint"}
              >
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
                defaultValue={deposit.memo || ""}
              />
            </Field>
          </ActionForm>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!window.confirm(`${deposit.name || "이 예적금"}을(를) 삭제할까요?`)) {
                return;
              }
              const fd = new FormData();
              fd.set("id", deposit.id);
              startDelete(async () => {
                setDelMsg(null);
                const res = await deleteDeposit(fd);
                setDelMsg(res.message);
                if (res.ok) router.refresh();
              });
            }}
          >
            <button
              type="submit"
              disabled={deleting}
              className="w-full rounded-xl bg-rose-50 px-4 py-3 text-sm font-extrabold text-up transition hover:bg-rose-100 disabled:opacity-60"
            >
              {deleting ? "삭제 중…" : "항목 삭제"}
            </button>
            {delMsg ? (
              <p role="status" className="mt-2 text-sm font-semibold text-muted">
                {delMsg}
              </p>
            ) : null}
          </form>
        </div>
      ) : null}
    </li>
  );
}
