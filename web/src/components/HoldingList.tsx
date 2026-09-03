import Link from "next/link";
import { SignedPct } from "@/components/SignedValue";
import { fmtKrw } from "@/lib/money";

type Item = {
  ticker: string;
  name: string;
  institution: string;
  value_krw: number | null;
  value: number | null;
  ccy: string;
  return_pct: number | null;
  qty: number;
};

function initials(name: string, ticker: string) {
  const src = (name || ticker || "?").trim();
  if (/^[A-Za-z.]+$/.test(src) && src.length <= 6) return src.slice(0, 2).toUpperCase();
  if (/^\d+$/.test(src) && src.length >= 2) return src.slice(-2);
  return Array.from(src)[0]?.toUpperCase() || "?";
}

export function HoldingList({
  items,
  linkable = false,
  query = "",
}: {
  items: Item[];
  linkable?: boolean;
  /** Preserve filters, e.g. `own=mine&inst=키움` */
  query?: string;
}) {
  if (!items.length) {
    return (
      <div className="rounded-2xl border border-dashed border-line bg-surface px-4 py-10 text-center text-sm text-muted">
        표시할 보유가 없습니다.{" "}
        <Link href="/record" className="font-semibold text-brand">
          더보기 → 기록하기
        </Link>
        에서 등록하세요.
      </div>
    );
  }

  const q = query ? `?${query}` : "";

  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-surface">
      {items.map((it) => {
        const valueLabel =
          it.value_krw != null
            ? fmtKrw(it.value_krw)
            : it.value != null
              ? it.ccy === "USD"
                ? `$${it.value.toLocaleString("en-US", {
                    maximumFractionDigits: 2,
                  })}`
                : fmtKrw(it.value)
              : "—";
        const inner = (
          <>
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-soft text-xs font-extrabold text-brand-dark">
              {initials(it.name, it.ticker)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[15px] font-extrabold tracking-tight">
                {it.name}
              </div>
              <div className="truncate text-xs text-muted">
                {it.ticker} · {it.institution}
                {it.qty && it.ticker !== "ISA-FUND"
                  ? ` · ${Number(it.qty).toLocaleString("ko-KR")}주`
                  : ""}
              </div>
            </div>
            <div className="shrink-0 text-right">
              <div className="text-[15px] font-extrabold tracking-tight">
                {valueLabel}
              </div>
              <div className="flex justify-end">
                <SignedPct value={it.return_pct} className="text-xs" />
              </div>
            </div>
          </>
        );
        const className =
          "flex items-center gap-3 border-b border-line px-4 py-3.5 last:border-b-0 touch-manipulation transition-transform active:scale-[0.99] active:bg-canvas";
        return linkable ? (
          <Link
            key={it.ticker}
            href={`/holdings/${encodeURIComponent(it.ticker)}${q}`}
            prefetch
            className={className}
          >
            {inner}
          </Link>
        ) : (
          <div key={it.ticker} className={className}>
            {inner}
          </div>
        );
      })}
    </div>
  );
}
