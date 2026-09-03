import { fmtMoney, signedArrow, signedTone } from "@/lib/money";

export function SignedAmount({
  amount,
  currency,
  className = "text-sm",
  kind = "pnl",
  signedNet = false,
}: {
  amount: number | null | undefined;
  currency?: string | null;
  className?: string;
  /** `flow` uses 유입/유출 labels; `pnl` uses 이익/손실. */
  kind?: "pnl" | "flow";
  /** When true, 0 has no arrow. Flow KPI cards omit this so ₩0 is still ↑. */
  signedNet?: boolean;
}) {
  if (amount === null || amount === undefined || Number.isNaN(Number(amount))) {
    return (
      <span
        className={`font-extrabold tracking-tight tabular-nums text-ink ${className}`}
      >
        —
      </span>
    );
  }
  const n = Number(amount);
  const zeroIsFlat = signedNet || kind === "pnl";
  if (zeroIsFlat && n === 0) {
    return (
      <span
        className={`font-extrabold tracking-tight tabular-nums text-ink ${className}`}
      >
        {fmtMoney(0, currency)}
      </span>
    );
  }
  const up = n >= 0;
  const abs = fmtMoney(Math.abs(n), currency);
  const word =
    kind === "flow" ? (up ? "유입" : "유출") : up ? "이익" : "손실";
  return (
    <span
      className={`inline-flex items-baseline gap-0.5 font-extrabold tracking-tight tabular-nums ${
        up ? "text-up" : "text-down"
      } ${className}`}
      aria-label={`${word} ${abs}`}
    >
      <span aria-hidden>{up ? "↑" : "↓"}</span>
      {abs}
    </span>
  );
}

export function SignedPct({
  value,
  className = "text-xs",
}: {
  value: number | null | undefined;
  className?: string;
}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return <span className={`font-bold text-muted ${className}`}>—</span>;
  }
  const n = Number(value);
  const tone = signedTone(n, { epsilon: 0.005 });
  const color =
    tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-muted";
  const arrow = signedArrow(tone);
  const body = `${Math.abs(n).toFixed(2)}%`;
  const word = tone === "up" ? "상승" : tone === "down" ? "하락" : "보합";
  return (
    <span
      className={`inline-flex items-baseline gap-0.5 font-bold tabular-nums ${color} ${className}`}
      aria-label={`${word} ${body}`}
    >
      {arrow ? <span aria-hidden>{arrow}</span> : null}
      {body}
    </span>
  );
}

export function FlowAmount({
  amount,
  className = "text-sm",
  signedNet = false,
}: {
  amount: number;
  className?: string;
  /** When true, 0 is unlabeled; otherwise treat >= 0 as inflow. */
  signedNet?: boolean;
}) {
  return (
    <SignedAmount
      amount={amount}
      className={className}
      kind="flow"
      signedNet={signedNet}
    />
  );
}
