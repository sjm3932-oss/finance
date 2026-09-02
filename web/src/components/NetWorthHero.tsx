import { fmtKrw, fmtPct, retTone } from "@/lib/money";
import type { NetWorth } from "@/lib/portfolio";

export function NetWorthHero({
  nw,
  returnPct,
}: {
  nw: NetWorth;
  returnPct: number | null;
}) {
  const tone = retTone(returnPct);
  const toneClass =
    tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-ink";

  const cells = [
    { label: "투자자산", value: fmtKrw(nw.invest) },
    { label: "현금·예수금", value: fmtKrw(nw.cash) },
    { label: "예적금", value: fmtKrw(nw.deposits) },
    { label: "기타자산", value: fmtKrw(nw.other) },
    { label: "부채", value: fmtKrw(nw.debt) },
    { label: "투자수익률", value: fmtPct(returnPct), tone },
    { label: "총자산", value: fmtKrw(nw.gross) },
  ];

  return (
    <section className="rounded-2xl border border-line bg-surface p-5 shadow-soft">
      <p className="text-xs font-semibold text-muted">순자산</p>
      <p className={`mt-1 text-3xl font-extrabold tracking-tight ${toneClass}`}>
        {fmtKrw(nw.net)}
      </p>
      <p className="mt-1 text-sm text-muted">투자 + 현금 + 예적금 + 기타 − 부채</p>
      <div className="mt-5 grid grid-cols-2 gap-3 border-t border-line pt-4 sm:grid-cols-3">
        {cells.map((c) => (
          <div key={c.label}>
            <div className="text-[11px] font-semibold text-muted">{c.label}</div>
            <div
              className={`mt-0.5 text-base font-extrabold tracking-tight ${
                c.tone === "up"
                  ? "text-up"
                  : c.tone === "down"
                    ? "text-down"
                    : "text-ink"
              }`}
            >
              {c.value}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
