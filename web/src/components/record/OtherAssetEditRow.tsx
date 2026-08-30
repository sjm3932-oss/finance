"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { deleteOtherAsset, updateOtherAsset } from "@/lib/actions/record";
import { ASSET_KIND_OPTIONS, OWNERSHIP_OPTIONS } from "@/lib/record";
import { ActionForm, Field, inputClass } from "@/components/record/FormUI";
import { fmtKrw, fmtPct, retTone } from "@/lib/money";
import { ASSET_KIND_KO, OWNERSHIP_KO, otherAssetReturn } from "@/lib/portfolio";

export type EditableOtherAsset = {
  id: string;
  name: string | null;
  asset_kind: string | null;
  value_krw: number | null;
  cost_krw?: number | null;
  ownership: string | null;
  memo?: string | null;
};

export function OtherAssetEditRow({ asset }: { asset: EditableOtherAsset }) {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const [delMsg, setDelMsg] = useState<string | null>(null);
  const [deleting, startDelete] = useTransition();

  const kindLabel =
    ASSET_KIND_KO[asset.asset_kind || ""] || asset.asset_kind || "기타";
  const ownLabel =
    OWNERSHIP_KO[asset.ownership || "joint"] || "공동";
  const ret = otherAssetReturn(asset);
  const tone = retTone(ret.pct);

  return (
    <li className="py-2.5">
      <div className="flex items-center justify-between gap-3 text-sm">
        <div className="min-w-0">
          <div className="font-extrabold tracking-tight">
            {asset.name || "기타자산"}
          </div>
          <div className="mt-0.5 text-xs font-semibold text-muted">
            {kindLabel} · {ownLabel} · 시세 {fmtKrw(asset.value_krw)}
            {ret.pct !== null ? ` · ${fmtPct(ret.pct)}` : ""}
          </div>
          {asset.memo ? (
            <p className="mt-1 text-xs text-muted">{asset.memo}</p>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {ret.pct !== null ? (
            <span
              className={`text-xs font-bold ${
                tone === "up"
                  ? "text-up"
                  : tone === "down"
                    ? "text-down"
                    : "text-muted"
              }`}
            >
              {fmtKrw(ret.pnl, { signed: true })}
            </span>
          ) : null}
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
              asset.id,
              asset.name,
              asset.asset_kind,
              asset.ownership,
              asset.value_krw,
              asset.cost_krw,
              asset.memo,
            ].join("|")}
            action={updateOtherAsset}
            submitLabel="저장"
          >
            <input type="hidden" name="id" value={asset.id} />
            <Field label="이름">
              <input
                name="name"
                required
                className={inputClass}
                defaultValue={asset.name || ""}
                autoComplete="off"
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="종류">
                <select
                  name="asset_kind"
                  className={inputClass}
                  defaultValue={asset.asset_kind || "other"}
                >
                  {ASSET_KIND_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="소유">
                <select
                  name="ownership"
                  className={inputClass}
                  defaultValue={asset.ownership || "joint"}
                >
                  {OWNERSHIP_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="매수가(원)">
                <input
                  name="cost_krw"
                  type="number"
                  min={0}
                  step={100000}
                  defaultValue={
                    asset.cost_krw != null && Number(asset.cost_krw) > 0
                      ? Number(asset.cost_krw)
                      : ""
                  }
                  placeholder="실제 산 가격"
                  className={inputClass}
                />
              </Field>
              <Field label="현재 시세(원)">
                <input
                  name="value_krw"
                  type="number"
                  min={0}
                  step={100000}
                  defaultValue={Number(asset.value_krw || 0)}
                  className={inputClass}
                />
              </Field>
            </div>
            <Field label="메모">
              <input
                name="memo"
                className={inputClass}
                defaultValue={asset.memo || ""}
                placeholder="예: 59.97A, 네이버 단지 링크"
              />
            </Field>
          </ActionForm>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (
                !window.confirm(
                  `${asset.name || "이 항목"}을(를) 삭제할까요?`
                )
              ) {
                return;
              }
              const fd = new FormData();
              fd.set("id", asset.id);
              startDelete(async () => {
                setDelMsg(null);
                const res = await deleteOtherAsset(fd);
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
