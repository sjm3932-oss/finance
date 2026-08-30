"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { invokeEdge } from "@/lib/edge";

type Job = {
  id: string;
  status: string;
  error?: string | null;
  result?: { accounts?: Array<{ currency: string; holdings: number; cash: number }> } | null;
};

export function TossSyncPanel() {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [workerIp, setWorkerIp] = useState<string | null>(null);
  const [workerOnline, setWorkerOnline] = useState(false);

  useEffect(() => {
    invokeEdge<{
      worker_ip?: string | null;
      worker_online?: boolean;
    }>("toss-sync", { probe: true })
      .then((res) => {
        setWorkerIp(res.worker_ip ?? null);
        setWorkerOnline(!!res.worker_online);
      })
      .catch(() => {
        setWorkerOnline(false);
      });
  }, []);

  function pollJob(jobId: string) {
    let n = 0;
    const tick = async () => {
      n += 1;
      const res = await invokeEdge<{ job?: Job }>("toss-sync", { job_id: jobId });
      const job = res.job;
      if (!job) return;
      if (job.status === "ok") {
        const parts = (job.result?.accounts || []).map(
          (a) => `${a.currency} ${a.holdings}종목 · 현금 ${a.cash}`
        );
        setMsg(
          parts.length
            ? `동기화 완료. ${parts.join(" / ")}`
            : "토스 계좌는 연결됐지만 보유 종목이 없습니다."
        );
        router.refresh();
        return;
      }
      if (job.status === "error") {
        setMsg(null);
        setErr(job.error || "동기화 실패");
        return;
      }
      if (n > 40) {
        setMsg(null);
        setErr(
          "클라우드 워커가 작업을 가져가지 않았습니다. 고정 IP VM에서 toss-sync-worker 가 켜져 있는지 확인하세요."
        );
        return;
      }
      setMsg(
        job.status === "running"
          ? "클라우드 워커가 토스 잔고를 가져오는 중…"
          : "클라우드 워커 대기 중…"
      );
      window.setTimeout(() => void tick(), 2000);
    };
    void tick();
  }

  function sync() {
    start(async () => {
      setErr(null);
      setMsg("클라우드 워커에 작업을 넣는 중…");
      try {
        const res = await invokeEdge<{
          job_id?: string;
          worker_online?: boolean;
          worker_ip?: string | null;
        }>("toss-sync", {});
        if (res.worker_ip) setWorkerIp(res.worker_ip);
        setWorkerOnline(!!res.worker_online);
        if (!res.job_id) throw new Error("작업 ID가 없습니다.");
        if (!res.worker_online) {
          setMsg(null);
          setErr(
            `클라우드 워커가 꺼져 있습니다.${res.worker_ip ? ` 등록 IP ${res.worker_ip}` : ""} 고정 IP VM에서 워커를 켜세요.`
          );
          return;
        }
        pollJob(res.job_id);
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
        워커가 켜져 있으면 몇 시간마다 잔고를 자동으로 가져옵니다. 지금 당장
        반영하려면 아래 버튼을 누르세요. 노트북에서 실행하지 않습니다.
      </p>
      {workerIp ? (
        <p className="mt-2 rounded-xl bg-canvas px-3 py-2 font-mono text-sm font-extrabold">
          워커 IP {workerIp}
          <span className="ml-2 text-xs font-semibold text-muted">
            {workerOnline ? "온라인" : "오프라인"}
          </span>
        </p>
      ) : (
        <p className="mt-2 text-xs text-muted">클라우드 워커가 아직 접속하지 않았습니다.</p>
      )}
      <button
        type="button"
        onClick={sync}
        disabled={pending}
        className="mt-3 w-full rounded-xl bg-brand px-4 py-3 text-sm font-extrabold text-white transition hover:bg-brand-dark disabled:opacity-60"
      >
        {pending ? "처리 중…" : "지금 동기화"}
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
