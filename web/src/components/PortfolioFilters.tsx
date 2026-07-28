"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { OWNERSHIP_KO } from "@/lib/portfolio";

const OWNER_OPTS = [
  { value: "전체", label: "전체" },
  { value: "joint", label: OWNERSHIP_KO.joint },
  { value: "mine", label: OWNERSHIP_KO.mine },
  { value: "spouse", label: OWNERSHIP_KO.spouse },
];

export function PortfolioFilters({
  institutions,
}: {
  institutions: string[];
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const own = params.get("own") || "전체";
  const inst = params.get("inst") || "전체";

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(params.toString());
    if (!value || value === "전체") next.delete(key);
    else next.set(key, value);
    const q = next.toString();
    router.push(q ? `${pathname}?${q}` : pathname);
  }

  const instOpts = ["전체", ...institutions];

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {OWNER_OPTS.map((o) => {
          const active = own === o.value;
          return (
            <button
              key={o.value}
              type="button"
              onClick={() => setParam("own", o.value)}
              className={`rounded-lg px-2.5 py-1.5 text-xs font-bold transition ${
                active
                  ? "bg-brand text-white"
                  : "bg-surface text-muted ring-1 ring-line"
              }`}
            >
              {o.label}
            </button>
          );
        })}
      </div>
      {instOpts.length > 1 ? (
        <div className="flex flex-wrap gap-1.5">
          {instOpts.map((name) => {
            const active = inst === name;
            return (
              <button
                key={name}
                type="button"
                onClick={() => setParam("inst", name)}
                className={`rounded-lg px-2.5 py-1.5 text-xs font-bold transition ${
                  active
                    ? "bg-ink text-white"
                    : "bg-surface text-muted ring-1 ring-line"
                }`}
              >
                {name}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
