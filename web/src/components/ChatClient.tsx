"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { invokeEdge } from "@/lib/edge";

type Source = { title: string; uri: string };
type Turn = {
  role: "user" | "model";
  content: string;
  sources?: Source[];
};

export function ChatClient({
  initialTurns = [],
}: {
  initialTurns?: Turn[];
}) {
  const [turns, setTurns] = useState<Turn[]>(initialTurns);
  const [input, setInput] = useState("");
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, pending]);

  function send() {
    const message = input.trim();
    if (!message || pending) return;
    setInput("");
    setError(null);
    const history = turns.map(({ role, content }) => ({ role, content }));
    setTurns((t) => [...t, { role: "user", content: message }]);

    start(async () => {
      try {
        const res = await invokeEdge<{
          reply: string;
          sources?: Source[];
        }>("wealth-chat", {
          message,
          history,
        });
        setTurns((t) => [
          ...t,
          {
            role: "model",
            content: res.reply,
            sources: res.sources || [],
          },
        ]);
      } catch (e) {
        setError(e instanceof Error ? e.message : "챗 실패");
        setTurns((t) => t.slice(0, -1));
        setInput(message);
      }
    });
  }

  return (
    <div className="flex min-h-[calc(100dvh-8rem)] flex-col">
      <div className="flex-1 space-y-3 overflow-y-auto pb-3">
        {!turns.length ? (
          <div className="rounded-2xl border border-dashed border-line bg-surface px-4 py-8 text-center text-sm text-muted">
            보유·시세·뉴스 근거로 객관적으로 답합니다.
            <br />
            예: 「내 QLD가 왜 떨어졌어?」
            <br />
            「코스피 하락 원인이 뭐야?」
          </div>
        ) : null}
        {turns.map((t, i) => (
          <div
            key={i}
            className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              t.role === "user"
                ? "ml-8 bg-brand text-white"
                : "mr-8 border border-line bg-surface"
            }`}
          >
            <div className="mb-1 text-[11px] font-bold opacity-70">
              {t.role === "user" ? "정명" : "부자뚱"}
            </div>
            <div className="whitespace-pre-wrap">{t.content}</div>
            {t.sources?.length ? (
              <ul className="mt-3 space-y-1 border-t border-line/80 pt-2 text-[11px] text-muted">
                {t.sources.slice(0, 5).map((s) => (
                  <li key={s.uri} className="truncate">
                    <a
                      href={s.uri}
                      target="_blank"
                      rel="noreferrer"
                      className="font-semibold text-brand underline-offset-2 hover:underline"
                    >
                      {s.title}
                    </a>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ))}
        {pending ? (
          <p className="text-center text-xs font-semibold text-brand">
            시세·뉴스 확인 후 답변 생성 중…
          </p>
        ) : null}
        {error ? (
          <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm font-semibold text-up">
            {error}
          </p>
        ) : null}
        <div ref={endRef} />
      </div>

      <div
        className="sticky z-30 border-t border-line bg-canvas/95 pt-3 backdrop-blur"
        style={{
          bottom: 0,
          paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))",
        }}
      >
        <div className="flex items-stretch gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="종목·시장 변동 이유를 물어보세요"
            disabled={pending}
            enterKeyHint="send"
            autoComplete="off"
            autoCorrect="off"
            className="min-h-12 min-w-0 flex-1 rounded-xl border border-line bg-surface px-3 text-base font-semibold outline-none focus:border-brand disabled:opacity-60"
          />
          <button
            type="button"
            onClick={send}
            disabled={pending || !input.trim()}
            className="shrink-0 rounded-xl bg-brand px-4 text-base font-extrabold text-white disabled:opacity-60"
          >
            전송
          </button>
        </div>
      </div>
    </div>
  );
}
