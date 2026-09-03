"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { invokeEdge } from "@/lib/edge";
import { Field, inputClass } from "@/components/record/FormUI";

const DEFAULT_ACCOUNTS = "64209634-01,64209634-21,64209634-22,64209634-29";

type AccountSummary = {
  currency: string;
  holdings: number;
  cash: number;
  trades?: number;
  dividends?: number;
  label?: string;
};

type ProductSummary = {
  code: string;
  label?: string;
  holdings: number;
  cash?: number;
  fund?: number;
  note?: string;
};

type JobResult = {
  accounts?: AccountSummary[];
  products?: ProductSummary[];
  trades?: number;
  dividends?: number;
};

function formatResult(result: JobResult): string {
  const accounts = result.accounts;
  const products = result.products;
  const totals = { trades: result.trades, dividends: result.dividends };
  const productBits = (products || []).map((p) => {
    const bits = [`${p.code} ${p.label || ""}`.trim()];
    if (Number(p.holdings || 0) > 0) bits.push(`${p.holdings}종목`);
    if (Number(p.fund || 0) > 0) bits.push("펀드");
    else if (p.note) bits.push(p.note);
    return bits.join(" ");
  });
  const accountTrades = (accounts || []).reduce((s, a) => s + Number(a.trades || 0), 0);
  const accountDivs = (accounts || []).reduce((s, a) => s + Number(a.dividends || 0), 0);
  const trades = Number(totals?.trades || 0) || accountTrades;
  const divs = Number(totals?.dividends || 0) || accountDivs;
  const parts = (accounts || []).map((a) => {
    return `${a.currency}${a.label ? ` ${a.label}` : ""} ${a.holdings}종목 · 현금 ${a.cash}`;
  });
  const extra = [
    trades ? `체결 ${trades}건` : "",
    divs ? `배당 ${divs}건` : "",
  ]
    .filter(Boolean)
    .join(" · ");
  const merged = parts.length
    ? `동기화 완료. ${parts.join(" / ")}${extra ? ` · ${extra}` : ""}`
    : extra
      ? `동기화 완료. ${extra}`
      : "한투 계좌는 연결됐지만 보유 종목이 없습니다.";
  return productBits.length ? `${merged}. ${productBits.join(" · ")}` : merged;
}

export function HankookSyncPanel() {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [configured, setConfigured] = useState(false);
  const [masked, setMasked] = useState("");
  const [appKey, setAppKey] = useState("");
  const [appSecret, setAppSecret] = useState("");
  const [accounts, setAccounts] = useState(DEFAULT_ACCOUNTS);

  useEffect(() => {
    invokeEdge<{
      configured?: boolean;
      app_key_masked?: string;
      accounts?: string;
      default_accounts?: string;
    }>("kis-sync", { probe: true })
      .then((res) => {
        setConfigured(!!res.configured);
        setMasked(res.app_key_masked || "");
        if (res.accounts) setAccounts(res.accounts);
        else if (res.default_accounts) setAccounts(res.default_accounts);
      })
      .catch(() => {
        setConfigured(false);
      });
  }, []);

  function save() {
    start(async () => {
      setErr(null);
      setMsg("앱키를 저장하는 중…");
      try {
        const res = await invokeEdge<{
          configured?: boolean;
          app_key_masked?: string;
          accounts?: string;
        }>("kis-sync", {
          save: true,
          app_key: appKey,
          app_secret: appSecret,
          accounts,
          env: "real",
        });
        setConfigured(!!res.configured);
        setMasked(res.app_key_masked || "");
        if (res.accounts) setAccounts(res.accounts);
        setAppSecret("");
        setAppKey("");
        setMsg("저장했습니다. 이제 지금 동기화를 누르면 됩니다. SSH나 Cloud Shell은 필요 없습니다.");
      } catch (e) {
        setMsg(null);
        setErr(e instanceof Error ? e.message : "저장 실패");
      }
    });
  }

  function sync() {
    start(async () => {
      setErr(null);
      try {
        if (!configured) {
          if (!appKey.trim() || !appSecret.trim()) {
            setErr("먼저 앱키와 앱시크릿을 붙여 넣고 키 저장을 누르세요.");
            return;
          }
          setMsg("앱키를 저장하는 중…");
          const saved = await invokeEdge<{
            configured?: boolean;
            app_key_masked?: string;
            accounts?: string;
          }>("kis-sync", {
            save: true,
            app_key: appKey,
            app_secret: appSecret,
            accounts,
            env: "real",
          });
          setConfigured(!!saved.configured);
          setMasked(saved.app_key_masked || "");
          if (saved.accounts) setAccounts(saved.accounts);
          setAppSecret("");
          setAppKey("");
        }
        setMsg("한투에서 잔고·체결·배당을 가져오는 중… 1~2분 걸릴 수 있습니다.");
        const res = await invokeEdge<JobResult & { ran?: boolean }>("kis-sync", {});
        setMsg(formatResult(res));
        router.refresh();
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
        SSH 키나 Cloud Shell이 필요 없습니다.{" "}
        <a
          href="https://apiportal.koreainvestment.com"
          className="font-semibold text-brand"
          target="_blank"
          rel="noreferrer"
        >
          KIS Developers
        </a>
        에서 받은 앱키·앱시크릿을 아래에 붙여 넣고 저장한 뒤, 지금 동기화를
        누르세요. 주문은 하지 않습니다.
      </p>
      <p className="mt-2 text-xs text-muted">
        계좌는 <span className="font-mono">8자리-상품코드</span> 입니다. 위탁 01,
        ISA 21, 개인연금 22, 퇴직연금 29를 각각 따로 가져옵니다. 홈 필터는{" "}
        <span className="font-semibold">정명 → 한국투자증권 → 01/21/22/29</span>
        로 고를 수 있습니다. ISA 펀드는 21 계좌 보유로 들어갑니다.
      </p>

      <div className="mt-3 space-y-3">
        <Field label="앱키">
          <input
            className={inputClass}
            value={appKey}
            onChange={(e) => setAppKey(e.target.value)}
            autoComplete="off"
            placeholder={masked ? `저장됨 ${masked}` : "KIS Developers 앱키"}
          />
        </Field>
        <Field label="앱시크릿">
          <input
            type="password"
            className={inputClass}
            value={appSecret}
            onChange={(e) => setAppSecret(e.target.value)}
            autoComplete="off"
            placeholder={configured ? "저장됨 · 바꾸려면 새로 입력" : "KIS Developers 앱시크릿"}
          />
        </Field>
        <Field label="계좌 (쉼표로 구분)">
          <input
            className={`${inputClass} font-mono text-xs`}
            value={accounts}
            onChange={(e) => setAccounts(e.target.value)}
            autoComplete="off"
          />
        </Field>
      </div>

      {configured ? (
        <p className="mt-3 rounded-xl bg-canvas px-3 py-2 text-sm font-semibold">
          저장됨
          {masked ? <span className="ml-2 font-mono text-xs text-muted">{masked}</span> : null}
        </p>
      ) : (
        <p className="mt-3 text-xs text-muted">아직 앱키가 저장되지 않았습니다.</p>
      )}

      <div className="mt-3 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={save}
          disabled={pending}
          className="rounded-xl bg-canvas px-4 py-3 text-sm font-extrabold text-ink ring-1 ring-line transition hover:bg-white disabled:opacity-60"
        >
          {pending ? "처리 중…" : "키 저장"}
        </button>
        <button
          type="button"
          onClick={sync}
          disabled={pending}
          className="rounded-xl bg-brand px-4 py-3 text-sm font-extrabold text-white transition hover:bg-brand-dark disabled:opacity-60"
        >
          {pending ? "처리 중…" : "지금 동기화"}
        </button>
      </div>
      <p className="mt-2 text-xs text-muted">
        한투 포털에서 IP 제한을 켜 두었다면 끄세요. (토스와 달리 한투는 보통 제한을
        켜지 않아도 됩니다.) 매일 오전 6시·오후 4시 자동 동기화는 GitHub Actions
        또는 워커가 같은 DB 키를 읽습니다.
      </p>
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
