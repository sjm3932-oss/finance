"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { deleteAccount, updateAccount } from "@/lib/actions/record";
import { ACCOUNT_TYPE_OPTIONS, OWNERSHIP_OPTIONS } from "@/lib/record";
import { ActionForm, Field, inputClass } from "@/components/record/FormUI";

export type EditableAccount = {
  id: string;
  institution: string | null;
  account_type: string | null;
  currency: string | null;
  cash_balance?: number | null;
  ownership?: string | null;
  memo?: string | null;
};

export function AccountEditRow({
  account,
  heading,
}: {
  account: EditableAccount;
  heading?: string;
}) {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const [delMsg, setDelMsg] = useState<string | null>(null);
  const [deleting, startDelete] = useTransition();

  const typeLabel =
    ACCOUNT_TYPE_OPTIONS.find((o) => o.value === account.account_type)?.label ||
    account.account_type ||
    "계좌";
  const ownLabel =
    OWNERSHIP_OPTIONS.find((o) => o.value === (account.ownership || "mine"))
      ?.label || "정명";

  return (
    <li className="py-2.5">
      <div className="flex items-center justify-between gap-3 text-sm">
        <div className="min-w-0">
          <div className="font-extrabold tracking-tight">
            {heading || account.institution || "계좌"}
          </div>
          <div className="mt-0.5 text-xs font-semibold text-muted">
            {typeLabel} · {account.currency || "KRW"} · {ownLabel}
          </div>
          {account.memo && account.memo !== heading ? (
            <p className="mt-1 text-xs text-muted">{account.memo}</p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => {
            setDelMsg(null);
            setOpen((v) => !v);
          }}
          className="shrink-0 rounded-lg px-2.5 py-1 text-xs font-extrabold text-brand ring-1 ring-line transition-transform active:scale-95"
        >
          {open ? "닫기" : "편집"}
        </button>
      </div>

      {open ? (
        <div className="mt-3 space-y-3 rounded-xl bg-canvas px-3 py-3">
          <ActionForm action={updateAccount} submitLabel="계좌 저장">
            <input type="hidden" name="account_id" value={account.id} />
            <Field label="금융기관">
              <input
                name="institution"
                required
                className={inputClass}
                defaultValue={account.institution || ""}
                autoComplete="off"
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="계좌유형">
                <select
                  name="account_type"
                  className={inputClass}
                  defaultValue={account.account_type || "brokerage"}
                >
                  {ACCOUNT_TYPE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="통화">
                <input
                  name="currency"
                  required
                  className={inputClass}
                  defaultValue={account.currency || "KRW"}
                  autoComplete="off"
                />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="현금/예수금">
                <input
                  name="cash_balance"
                  type="number"
                  min={0}
                  step={10000}
                  defaultValue={Number(account.cash_balance || 0)}
                  className={inputClass}
                />
              </Field>
              <Field label="소유">
                <select
                  name="ownership"
                  className={inputClass}
                  defaultValue={account.ownership || "mine"}
                >
                  {OWNERSHIP_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="메모">
              <input
                name="memo"
                className={inputClass}
                defaultValue={account.memo || ""}
                placeholder="예: ISA, 계좌 끝자리 1234"
              />
            </Field>
          </ActionForm>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (
                !window.confirm(
                  `${account.institution || "이 계좌"}를 삭제할까요? 이 계좌의 보유·매매도 함께 지워집니다.`
                )
              ) {
                return;
              }
              const fd = new FormData();
              fd.set("account_id", account.id);
              startDelete(async () => {
                setDelMsg(null);
                const res = await deleteAccount(fd);
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
              {deleting ? "삭제 중…" : "계좌 삭제"}
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
