"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { invokeEdge } from "@/lib/edge";

export function TossSyncPanel() {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ip, setIp] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    invokeEdge<{ egress_ip?: string | null }>("toss-sync", { probe: true })
      .then((res) => {
        if (res.egress_ip) setIp(res.egress_ip);
      })
      .catch(() => {
        /* probe is optional; sync error still shows the IP */
      });
  }, []);

  function copyIp() {
    if (!ip) return;
    void navigator.clipboard.writeText(ip).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    });
  }

  function sync() {
    start(async () => {
      setErr(null);
      setMsg("토스증권 잔고를 가져오는 중…");
      try {
        const res = await invokeEdge<{
          accounts?: Array<{ currency: string; holdings: number; cash: number }>;
          egress_ip?: string | null;
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
        토스 WTS → 설정 → Open API → 허용 IP에 아래 주소를 등록한 뒤 잔고를
        가져옵니다. 주문은 하지 않습니다. Edge 출구 IP는 바뀔 수 있습니다.
      </p>
      {ip ? (
        <div className="mt-3 flex items-center gap-2 rounded-xl bg-canvas px-3 py-2">
          <div className="min-w-0 flex-1">
            <div className="text-[11px] font-semibold text-muted">지금 호출 IP</div>
            <div className="truncate font-mono text-sm font-extrabold tracking-tight">
              {ip}
            </div>
          </div>
          <button
            type="button"
            onClick={copyIp}
            className="shrink-0 rounded-full border border-line bg-surface px-3 py-1.5 text-xs font-bold"
          >
            {copied ? "복사됨" : "복사"}
          </button>
        </div>
      ) : (
        <p className="mt-2 text-xs text-muted">호출 IP를 확인하는 중…</p>
      )}
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
