"use client";

import { useMemo, useTransition } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  OWNERSHIP_KO,
  institutionsForOwnership,
  type AccountRow,
} from "@/lib/portfolio";

const OWNER_OPTS = [
  { value: "전체", label: "전체" },
  { value: "joint", label: OWNERSHIP_KO.joint },
  { value: "mine", label: OWNERSHIP_KO.mine },
  { value: "spouse", label: OWNERSHIP_KO.spouse },
];

export function PortfolioFilters({
  accounts,
}: {
  accounts: Array<Pick<AccountRow, "institution" | "ownership">>;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, start] = useTransition();
  const own = params.get("own") || "전체";
  const inst = params.get("inst") || "전체";

  const childInstitutions = useMemo(
    () => institutionsForOwnership(accounts, own === "전체" ? null : own),
    [accounts, own]
  );
  const ownLabel = OWNER_OPTS.find((o) => o.value === own)?.label || "전체";

  function navigate(nextOwn: string, nextInst: string) {
    const next = new URLSearchParams(params.toString());
    if (!nextOwn || nextOwn === "전체") next.delete("own");
    else next.set("own", nextOwn);
    if (!nextInst || nextInst === "전체") next.delete("inst");
    else next.set("inst", nextInst);
    const q = next.toString();
    start(() => {
      router.push(q ? `${pathname}?${q}` : pathname);
    });
  }

  function selectOwn(value: string) {
    const children = institutionsForOwnership(
      accounts,
      value === "전체" ? null : value
    );
    const nextInst =
      inst !== "전체" && children.includes(inst) ? inst : "전체";
    navigate(value, nextInst);
  }

  const instOpts = ["전체", ...childInstitutions];

  return (
    <div className={`space-y-2 ${pending ? "opacity-70" : ""}`}>
      {pending ? (
        <p className="text-[11px] font-semibold text-brand">필터 적용 중…</p>
      ) : null}
      <div>
        <p className="mb-1.5 text-[11px] font-semibold text-muted">소유</p>
        <div className="flex flex-wrap gap-1.5">
          {OWNER_OPTS.map((o) => {
            const active = own === o.value;
            return (
              <button
                key={o.value}
                type="button"
                disabled={pending}
                aria-pressed={active}
                onClick={() => selectOwn(o.value)}
                className={`min-h-9 rounded-lg px-3 py-2 text-xs font-bold transition disabled:cursor-wait ${
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
      </div>
      <div className="border-l-2 border-line pl-3">
        <p className="mb-1.5 text-[11px] font-semibold text-muted">
          {own === "전체" ? "금융기관" : `${ownLabel} · 금융기관`}
        </p>
        {childInstitutions.length ? (
          <div className="flex flex-wrap gap-1.5">
            {instOpts.map((name) => {
              const active = inst === name;
              return (
                <button
                  key={name}
                  type="button"
                  disabled={pending}
                  aria-pressed={active}
                  onClick={() => navigate(own, name)}
                  className={`min-h-9 rounded-lg px-3 py-2 text-xs font-bold transition disabled:cursor-wait ${
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
        ) : (
          <p className="text-[11px] text-muted">
            등록된 금융기관이 없습니다.
          </p>
        )}
      </div>
      {inst !== "전체" ? (
        <p className="text-[11px] text-muted">
          계좌 필터 중에는 기타자산·부채가 순자산에서 제외됩니다.
        </p>
      ) : null}
    </div>
  );
}
