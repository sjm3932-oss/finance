"use client";

import {
  upsertWatchlistItem,
  deleteWatchlistItem,
  acknowledgeWatchAlerts,
  evaluateWatchAlerts,
} from "@/lib/actions/watchTax";
import { ActionForm, Field, Panel, inputClass } from "@/components/record/FormUI";
import { useTransition, useState } from "react";

type Item = {
  id: string;
  ticker: string;
  name: string | null;
  target_price: number | null;
  stop_price: number | null;
  note: string | null;
  price: number | null;
  currency: string | null;
};

type Alert = {
  id: string;
  ticker: string;
  alert_kind: string;
  trigger_price: number | null;
  market_price: number | null;
};

function priceLabel(price: number | null, ticker: string, ccy: string | null) {
  if (price == null) return "—";
  const krw = (ccy || "").toUpperCase() === "KRW" || /^\d{6}$/.test(ticker);
  return krw
    ? `₩${Math.round(price).toLocaleString("ko-KR")}`
    : `$${price.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
}

export function WatchlistForms({
  items,
  alerts,
}: {
  items: Item[];
  alerts: Alert[];
}) {
  const [pending, start] = useTransition();
  const [msg, setMsg] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      {alerts.length ? (
        <Panel title="가격 알림">
          <div className="space-y-2">
            {alerts.map((a) => (
              <div key={a.id} className="rounded-xl bg-canvas px-3 py-2 text-sm">
                <div className="font-extrabold">
                  {a.alert_kind === "stop" ? "손절가 도달" : "목표가 도달"} ·{" "}
                  {a.ticker}
                </div>
                <div className="text-xs text-muted">
                  기준 {a.trigger_price} / 현재 {a.market_price}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3">
            <button
              type="button"
              disabled={pending}
              className="w-full rounded-xl border border-line px-4 py-2.5 text-sm font-bold disabled:opacity-60"
              onClick={() =>
                start(async () => {
                  const res = await acknowledgeWatchAlerts();
                  setMsg(res.message);
                })
              }
            >
              알림 모두 확인
            </button>
          </div>
        </Panel>
      ) : null}

      <Panel title="관심종목 추가 · 수정">
        <p className="mb-3 text-xs text-muted">
          같은 티커를 다시 저장하면 목표가·손절가가 덮어씌워집니다.
        </p>
        <ActionForm action={upsertWatchlistItem} submitLabel="저장">
          <div className="grid grid-cols-2 gap-3">
            <Field label="티커">
              <input
                name="ticker"
                required
                className={inputClass}
                placeholder="005930 / AAPL"
              />
            </Field>
            <Field label="종목명">
              <input name="name" className={inputClass} placeholder="선택" />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="목표가">
              <input
                name="target_price"
                type="number"
                min={0}
                step="any"
                className={inputClass}
                placeholder="없으면 비움"
              />
            </Field>
            <Field label="손절가">
              <input
                name="stop_price"
                type="number"
                min={0}
                step="any"
                className={inputClass}
                placeholder="없으면 비움"
              />
            </Field>
          </div>
          <Field label="메모">
            <input name="note" className={inputClass} />
          </Field>
        </ActionForm>
      </Panel>

      <div className="flex gap-2">
        <button
          type="button"
          disabled={pending}
          className="flex-1 rounded-xl bg-ink px-4 py-3 text-sm font-extrabold text-white disabled:opacity-60"
          onClick={() =>
            start(async () => {
              const res = await evaluateWatchAlerts();
              setMsg(res.message);
            })
          }
        >
          목표가·손절 지금 검사
        </button>
      </div>
      {msg ? (
        <p className="rounded-xl bg-brand-soft px-3 py-2 text-sm font-semibold text-brand-dark">
          {msg}
        </p>
      ) : null}

      <Panel title={`등록된 관심 (${items.length})`}>
        {!items.length ? (
          <p className="text-sm text-muted">등록된 관심종목이 없습니다.</p>
        ) : (
          <div className="space-y-3">
            {items.map((it) => (
              <div key={it.id} className="rounded-xl bg-canvas p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-extrabold">
                      {it.name || it.ticker}
                    </div>
                    <div className="text-xs text-muted">
                      {it.ticker}
                      {it.note ? ` · ${it.note}` : ""}
                    </div>
                    <div className="mt-1 text-xs font-bold text-muted">
                      현재 {priceLabel(it.price, it.ticker, it.currency)} · 목표{" "}
                      {priceLabel(it.target_price, it.ticker, it.currency)} · 손절{" "}
                      {priceLabel(it.stop_price, it.ticker, it.currency)}
                    </div>
                  </div>
                </div>
                <div className="mt-2">
                  <ActionForm action={deleteWatchlistItem} submitLabel="삭제">
                    <input type="hidden" name="id" value={it.id} />
                  </ActionForm>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
