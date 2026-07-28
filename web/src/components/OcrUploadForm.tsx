"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { invokeEdge } from "@/lib/edge";
import { Field, inputClass, Panel } from "@/components/record/FormUI";

type Account = { id: string; institution: string | null };

export function OcrUploadForm({ accounts }: { accounts: Account[] }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const file = fd.get("file");
    if (!(file instanceof File) || !file.size) {
      setErr("이미지 파일을 선택하세요.");
      return;
    }
    const accountId = String(fd.get("account_id") || "");
    const docType = String(fd.get("doc_type") || "auto");

    start(async () => {
      setErr(null);
      setMsg("업로드 · AI 인식 중… (수 초 걸릴 수 있어요)");
      try {
        const supabase = createClient();
        const {
          data: { user },
        } = await supabase.auth.getUser();
        if (!user) throw new Error("로그인이 필요합니다.");

        const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
        const safe = file.name.replace(/\//g, "_");
        const path = `${user.id}/${stamp}_${crypto.randomUUID().replace(/-/g, "")}_${safe}`;
        const mime = file.type || "image/png";

        const { error: upErr } = await supabase.storage
          .from("ocr-screenshots")
          .upload(path, file, { contentType: mime, upsert: false });
        if (upErr) throw new Error(upErr.message);

        const result = await invokeEdge<{
          staging_id: string;
          status: string;
          error_msg?: string | null;
        }>("ocr-parse", {
          image_path: path,
          account_id: accountId || null,
          doc_type: docType,
          mime_type: mime,
        });

        if (result.status === "failed") {
          setMsg(
            `인식 실패로 스테이징에 저장됨. ${result.error_msg || ""} 검토 화면에서 확인하세요.`
          );
        } else {
          setMsg("인식 완료. 검토 화면으로 이동합니다…");
        }
        router.push(`/ocr/review?id=${result.staging_id}`);
        router.refresh();
      } catch (e) {
        setErr(e instanceof Error ? e.message : "업로드 실패");
        setMsg(null);
      }
    });
  }

  return (
    <Panel title="스크린샷 OCR">
      <p className="mb-3 text-xs text-muted">
        이미지를 Supabase Storage에 올린 뒤 Edge Function이 Gemini로 인식합니다.
        Gemini 키는 Vercel이 아니라 Supabase Function secrets에 둡니다.
      </p>
      <form className="space-y-3" onSubmit={onSubmit}>
        <Field label="이미지">
          <input
            name="file"
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            required
            className={inputClass}
            disabled={pending}
          />
        </Field>
        <Field label="문서 유형">
          <select name="doc_type" className={inputClass} defaultValue="auto" disabled={pending}>
            <option value="auto">자동</option>
            <option value="holdings">보유</option>
            <option value="trades">매매</option>
            <option value="dividends">배당</option>
            <option value="debt">부채</option>
          </select>
        </Field>
        <Field label="연결 계좌 (권장)">
          <select name="account_id" className={inputClass} defaultValue="" disabled={pending}>
            <option value="">선택 안 함</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.institution || a.id}
              </option>
            ))}
          </select>
        </Field>
        <button
          type="submit"
          disabled={pending}
          className="w-full rounded-xl bg-brand px-4 py-3 text-sm font-extrabold text-white disabled:opacity-60"
        >
          {pending ? "처리 중…" : "업로드 · 인식"}
        </button>
      </form>
      {msg ? (
        <p className="mt-3 rounded-xl bg-brand-soft px-3 py-2 text-sm font-semibold text-brand-dark">
          {msg}
        </p>
      ) : null}
      {err ? (
        <p className="mt-3 rounded-xl bg-rose-50 px-3 py-2 text-sm font-semibold text-up">
          {err}
        </p>
      ) : null}
    </Panel>
  );
}
