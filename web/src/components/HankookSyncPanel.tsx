"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { invokeEdge } from "@/lib/edge";

type Job = {
  id: string;
  status: string;
  error?: string | null;
  result?: {
    accounts?: Array<{
      currency: string;
      holdings: number;
      cash: number;
      trades?: number;
      dividends?: number;
    }>;
  } | null;
};

export function HankookSyncPanel() {
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
    }>("kis-sync", { probe: true })
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
      const res = await invokeEdge<{ job?: Job }>("kis-sync", { job_id: jobId });
      const job = res.job;
      if (!job) return;
      if (job.status === "ok") {
        const parts = (job.result?.accounts || []).map((a) => {
          const trades = Number(a.trades || 0);
          const divs = Number(a.dividends || 0);
          const extra = [
            trades ? `체결 ${trades}건` : "",
            divs ? `배당 ${divs}건` : "",
          ]
            .filter(Boolean)
            .join(" · ");
          return `${a.currency} ${a.holdings}종목 · 현금 ${a.cash}${extra ? ` · ${extra}` : ""}`;
        });
        setMsg(
          parts.length
            ? `동기화 완료. ${parts.join(" / ")}`
            : "한투 계좌는 연결됐지만 보유 종목이 없습니다."
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
          "클라우드 워커가 작업을 가져가지 않았습니다. 고정 IP VM에서 toss-sync-worker 를 최신 코드로 재시작했는지 확인하세요."
        );
        return;
      }
      setMsg(
        job.status === "running"
          ? "클라우드 워커가 한투 잔고·체결·배당을 가져오는 중…"
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
        }>("kis-sync", {});
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
      <div className="font-extrabold tracking-tight">한국투자증권 동기화</div>
      <p className="mt-1 text-sm text-muted">
        워커가 켜져 있고 한투 앱키·계좌가 등록돼 있으면 매일 오전 6시·오후
        4시(한국 시간)에 잔고·체결·배당을 가져옵니다. 지금 당장 반영하려면 아래
        버튼을 누르세요.
      </p>
      <p className="mt-2 text-xs text-muted">
        앱키는{" "}
        <a
          href="https://apiportal.koreainvestment.com"
          className="font-semibold text-brand"
          target="_blank"
          rel="noreferrer"
        >
          KIS Developers
        </a>
        에서 한 번 휴대폰 인증 후 발급합니다. 워커 환경변수{" "}
        <span className="font-mono">KIS_APP_KEY</span>,{" "}
        <span className="font-mono">KIS_APP_SECRET</span>,{" "}
        <span className="font-mono">KIS_CANO</span> (계좌 8자리, 상품코드는 기본
        01)가 필요합니다.
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
