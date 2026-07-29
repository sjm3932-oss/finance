"use client";

import { useState, useTransition } from "react";
import { saveOcrStaging, setOcrStatus } from "@/lib/actions/ocr";
import { Field, Panel, inputClass } from "@/components/record/FormUI";

type Staging = {
  id: string;
  status: string;
  image_url: string | null;
  parsed_json: unknown;
  created_at?: string | null;
  signed_url?: string | null;
};

export function OcrReviewPanel({
  items,
  focusId,
}: {
  items: Staging[];
  focusId?: string | null;
}) {
  const ordered = [...items].sort((a, b) => {
    if (focusId && a.id === focusId) return -1;
    if (focusId && b.id === focusId) return 1;
    return 0;
  });

  if (!ordered.length) {
    return (
      <div className="rounded-2xl border border-dashed border-line bg-surface px-4 py-10 text-center text-sm text-muted">
        대기 중인 OCR 항목이 없습니다.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {ordered.map((it) => (
        <OcrReviewCard key={it.id} item={it} />
      ))}
    </div>
  );
}

function OcrReviewCard({ item }: { item: Staging }) {
  const [jsonText, setJsonText] = useState(
    JSON.stringify(item.parsed_json ?? {}, null, 2)
  );
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [pending, start] = useTransition();

  function run(
    action: (fd: FormData) => Promise<{ ok: boolean; message: string }>,
    status?: string
  ) {
    start(async () => {
      const fd = new FormData();
      fd.set("id", item.id);
      fd.set("parsed_json", jsonText);
      if (status) fd.set("status", status);
      const res = await action(fd);
      setMsg({ ok: res.ok, text: res.message });
    });
  }

  return (
    <Panel title={`${item.status} · ${item.id.slice(0, 8)}`}>
      <p className="mb-2 text-xs text-muted">
        {item.created_at ? String(item.created_at).slice(0, 19) : ""} ·{" "}
        {item.image_url}
      </p>
      {item.signed_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={item.signed_url}
          alt="OCR screenshot"
          className="mb-3 max-h-56 w-full rounded-xl bg-canvas object-contain"
        />
      ) : null}
      <Field label="parsed_json">
        <textarea
          rows={14}
          value={jsonText}
          onChange={(e) => setJsonText(e.target.value)}
          className={`${inputClass} font-mono text-xs`}
          disabled={pending}
        />
      </Field>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <button
          type="button"
          disabled={pending}
          onClick={() => run(saveOcrStaging)}
          className="rounded-xl border border-line px-3 py-2.5 text-xs font-extrabold disabled:opacity-60"
        >
          저장
        </button>
        <button
          type="button"
          disabled={pending}
          onClick={() => run(setOcrStatus, "approved")}
          className="rounded-xl bg-brand px-3 py-2.5 text-xs font-extrabold text-white disabled:opacity-60"
        >
          승인
        </button>
        <button
          type="button"
          disabled={pending}
          onClick={() => run(setOcrStatus, "rejected")}
          className="rounded-xl bg-ink px-3 py-2.5 text-xs font-extrabold text-white disabled:opacity-60"
        >
          거절
        </button>
      </div>
      {msg ? (
        <p
          className={`mt-2 rounded-xl px-3 py-2 text-sm font-semibold ${
            msg.ok
              ? "bg-brand-soft text-brand-dark"
              : "bg-rose-50 text-up"
          }`}
        >
          {msg.text}
        </p>
      ) : null}
      <p className="mt-2 text-[11px] text-muted">
        승인 전 JSON에 account_id(계좌 UUID)가 있는지 확인하세요. 부채만 있으면
        계좌 없이도 됩니다.
      </p>
    </Panel>
  );
}
