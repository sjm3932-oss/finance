"use client";

import { useEffect } from "react";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="space-y-4 px-0 pt-2">
      <div className="rounded-2xl border border-line bg-surface p-5 shadow-soft">
        <h1 className="text-lg font-extrabold tracking-tight">
          화면을 불러오지 못했어요
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          {error.message?.includes("데이터 로드")
            ? error.message
            : "잠시 후 다시 시도해 주세요. 문제가 계속되면 로그인 상태를 확인해 주세요."}
        </p>
        <button
          type="button"
          onClick={reset}
          className="mt-5 w-full rounded-xl bg-brand px-4 py-3 text-sm font-extrabold text-white"
        >
          다시 시도
        </button>
      </div>
    </div>
  );
}
