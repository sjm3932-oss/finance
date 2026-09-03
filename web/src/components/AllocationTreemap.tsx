"use client";

import { useMemo, useState } from "react";
import { buildTreemapLeaves, returnColor, type TreemapLeaf } from "@/lib/insights";
import type { LiveHolding } from "@/lib/portfolio";
import { fmtKrw, fmtPctArrow } from "@/lib/money";

function layoutStrip(
  leaves: TreemapLeaf[],
  width: number,
  height: number
): Array<TreemapLeaf & { x: number; y: number; w: number; h: number }> {
  const total = leaves.reduce((s, l) => s + l.value, 0) || 1;
  const out: Array<TreemapLeaf & { x: number; y: number; w: number; h: number }> =
    [];
  // Two-row strip: big items on top row, rest bottom
  const topN = Math.min(4, leaves.length);
  const top = leaves.slice(0, topN);
  const bottom = leaves.slice(topN);
  const topSum = top.reduce((s, l) => s + l.value, 0) || 1;
  const topH = bottom.length ? height * 0.58 : height;
  let x = 0;
  for (const leaf of top) {
    const w = (leaf.value / topSum) * width;
    out.push({ ...leaf, x, y: 0, w: Math.max(w, 2), h: topH });
    x += w;
  }
  if (bottom.length) {
    const botSum = bottom.reduce((s, l) => s + l.value, 0) || 1;
    const botH = height - topH;
    x = 0;
    for (const leaf of bottom) {
      const w = (leaf.value / botSum) * width;
      out.push({ ...leaf, x, y: topH, w: Math.max(w, 2), h: botH });
      x += w;
    }
  }
  void total;
  return out;
}

export function AllocationTreemap({ live }: { live: LiveHolding[] }) {
  const [mode, setMode] = useState<"ticker" | "region" | "account">("ticker");
  const leaves = useMemo(() => buildTreemapLeaves(live, mode), [live, mode]);
  const W = 360;
  const H = 220;
  const laid = useMemo(() => layoutStrip(leaves, W, H), [leaves]);

  if (!leaves.length) {
    return (
      <section className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
        <h2 className="text-base font-extrabold tracking-tight">자산 배분 트리맵</h2>
        <p className="mt-2 text-sm text-muted">표시할 보유가 없습니다.</p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
      <div className="flex items-end justify-between gap-2">
        <div>
          <h2 className="text-base font-extrabold tracking-tight">자산 배분 트리맵</h2>
          <p className="mt-0.5 text-xs text-muted">크기=평가액 · 색=수익률</p>
        </div>
        <div className="flex gap-1">
          {(
            [
              ["ticker", "종목"],
              ["region", "국내/해외"],
              ["account", "계좌"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setMode(id)}
              className={`rounded-lg px-2 py-1 text-[11px] font-bold ${
                mode === id ? "bg-brand text-white" : "bg-canvas text-muted"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 w-full overflow-hidden rounded-xl">
        {laid.map((n) => {
          const fill = returnColor(n.return_pct);
          const showLabel = n.w > 42 && n.h > 28;
          return (
            <g key={n.id}>
              <rect
                x={n.x + 1}
                y={n.y + 1}
                width={Math.max(n.w - 2, 0)}
                height={Math.max(n.h - 2, 0)}
                fill={fill}
                opacity={0.85}
                rx={6}
              />
              {showLabel ? (
                <text
                  x={n.x + 8}
                  y={n.y + 18}
                  fill="#fff"
                  fontSize="11"
                  fontWeight="700"
                >
                  {n.label.length > 8 ? n.label.slice(0, 8) : n.label}
                </text>
              ) : null}
              {showLabel && n.h > 44 ? (
                <text
                  x={n.x + 8}
                  y={n.y + 34}
                  fill="#fff"
                  fontSize="10"
                  fontWeight="600"
                  opacity={0.9}
                >
                  {fmtPctArrow(n.return_pct)}
                </text>
              ) : null}
            </g>
          );
        })}
      </svg>
      <p className="mt-2 text-[11px] text-muted">
        합계 {fmtKrw(leaves.reduce((s, l) => s + l.value, 0))} · {leaves.length}종목
      </p>
    </section>
  );
}
