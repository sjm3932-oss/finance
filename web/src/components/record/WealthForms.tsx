"use client";

import { createOtherAsset } from "@/lib/actions/record";
import { ASSET_KIND_OPTIONS, OWNERSHIP_OPTIONS } from "@/lib/record";
import { ActionForm, Field, Panel, inputClass } from "@/components/record/FormUI";
import { OtherAssetEditRow } from "@/components/record/OtherAssetEditRow";
import type { OtherAssetRow } from "@/lib/portfolio";
import Link from "next/link";

export function WealthForms({ otherAssets }: { otherAssets: OtherAssetRow[] }) {
  const withId = otherAssets.filter(
    (o): o is OtherAssetRow & { id: string } => Boolean(o.id)
  );

  return (
    <div className="space-y-4">
      <Panel title="부동산 · 기타자산 추가">
        <p className="mb-3 text-xs text-muted">
          아파트·주택은 종류를 부동산으로 두고, 매수가와 현재 시세를 넣으면
          수익률이 나옵니다. 예적금은{" "}
          <Link href="/record?tab=deposit" className="font-semibold text-brand">
            예적금 탭
          </Link>
          에서 이율·만기를 관리하세요.
        </p>
        <ActionForm action={createOtherAsset} submitLabel="추가">
          <Field label="이름">
            <input name="name" required className={inputClass} placeholder="예: 아파트" />
          </Field>
          <Field label="종류">
            <select name="asset_kind" className={inputClass} defaultValue="real_estate">
              {ASSET_KIND_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="매수가(원)">
              <input
                name="cost_krw"
                type="number"
                min={0}
                step={100000}
                className={inputClass}
                placeholder="실제 산 가격"
              />
            </Field>
            <Field label="현재 시세(원)">
              <input
                name="value_krw"
                type="number"
                min={0}
                step={100000}
                defaultValue={0}
                className={inputClass}
              />
            </Field>
          </div>
          <Field label="소유">
            <select name="ownership" className={inputClass} defaultValue="joint">
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
              placeholder="예: 59.97A, 네이버 단지 링크"
            />
          </Field>
        </ActionForm>
      </Panel>

      <Panel title={`등록된 기타자산 (${withId.length})`}>
        {!withId.length ? (
          <p className="text-sm text-muted">아직 기타자산이 없습니다.</p>
        ) : (
          <>
            <p className="-mt-1 mb-2 text-xs text-muted">
              이름·종류·소유·매수가·시세·메모를 행마다 수정할 수 있습니다.
            </p>
            <ul className="divide-y divide-line">
              {withId.map((asset) => (
                <OtherAssetEditRow key={asset.id} asset={asset} />
              ))}
            </ul>
          </>
        )}
      </Panel>
    </div>
  );
}
