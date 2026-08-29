"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { invokeEdge } from "@/lib/edge";

export function TossSyncPanel() {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  function sync() {
    start(async () => {
      setErr(null);
      setMsg("토스증권 잔고를 가져오는 중…");
      try {
        const res = await invokeEdge<{
          accounts?: Array<{ currency: string; holdings: number; cash: number }>;
        }>("toss-sync", {});
        const parts = (res.accounts || []).map(
          (a) => `${a.currency} ${a.holdings}종목 · 현금 ${a.cash}`
        );
        setMsg(
          parts.length
            ? `동기화 완료. ${parts.join(" / ")}`
            : "토스 계좌는 연결됐지만 보유 종목이 없습니다."
        );
        router.refresh();
      } catch (e) {
        setMsg(null);
        setErr(e instanceof Error ? e.message : "동기화 실패");
      }
    });
  }

  return (
    <div className="rounded-2xl border border-line bg-surface px-4 py-4 shadow-soft">
      <div className="font-extrabold tracking-tight">토스증권 동기화</div>
      <p className="mt-1 text-sm text-muted">
        WTS 설정 → Open API에서 키를 발급하고, 호출 IP를 허용 목록에 넣은 뒤
        잔고를 가져옵니다. 주문은 하지 않습니다.
      </p>
      <button
        type="button"
        onClick={sync}
        disabled={pending}
        className="mt-3 w-full rounded-xl bg-brand px-4 py-3 text-sm font-extrabold text-white transition hover:bg-brand-dark disabled:opacity-60"
      >
        {pending ? "동기화 중…" : "지금 동기화"}
      </button>
      {msg ? (
        <p role="status" className="mt-2 rounded-xl bg-brand-soft px-3 py-2 text-sm font-semibold text-brand-dark">
          {msg}
        </p>
      ) : null}
      {err ? (
        <p role="status" className="mt-2 rounded-xl bg-rose-50 px-3 py-2 text-sm font-semibold text-up">
          {err}
        </p>
      ) : null}
    </div>
  );
}
