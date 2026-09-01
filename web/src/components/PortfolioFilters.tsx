"use client";

import { useMemo, useTransition } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  OWNERSHIP_KO,
  institutionsForOwnership,
  subsForInstitution,
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
  accounts: Array<Pick<AccountRow, "id" | "institution" | "ownership" | "memo" | "currency">>;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, start] = useTransition();
  const own = params.get("own") || "전체";
  const inst = params.get("inst") || "전체";
  const sub = params.get("sub") || "전체";

  const childInstitutions = useMemo(
    () => institutionsForOwnership(accounts, own === "전체" ? null : own),
    [accounts, own]
  );
  const ownLabel = OWNER_OPTS.find((o) => o.value === own)?.label || "전체";
  const childSubs = useMemo(() => {
    if (!inst || inst === "전체") return [];
    return subsForInstitution(accounts as AccountRow[], inst, own === "전체" ? null : own);
  }, [accounts, inst, own]);

  function navigate(nextOwn: string, nextInst: string, nextSub: string) {
    const next = new URLSearchParams(params.toString());
    if (!nextOwn || nextOwn === "전체") next.delete("own");
    else next.set("own", nextOwn);
    if (!nextInst || nextInst === "전체") next.delete("inst");
    else next.set("inst", nextInst);
    if (!nextSub || nextSub === "전체" || !nextInst || nextInst === "전체") next.delete("sub");
    else next.set("sub", nextSub);
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
    const nextSubs =
      nextInst !== "전체"
        ? subsForInstitution(accounts as AccountRow[], nextInst, value === "전체" ? null : value)
        : [];
    const nextSub =
      sub !== "전체" && nextSubs.some((s) => s.key === sub) ? sub : "전체";
    navigate(value, nextInst, nextSub);
  }

  function selectInst(name: string) {
    const nextSubs =
      name !== "전체"
        ? subsForInstitution(accounts as AccountRow[], name, own === "전체" ? null : own)
        : [];
    const nextSub =
      sub !== "전체" && nextSubs.some((s) => s.key === sub) ? sub : "전체";
    navigate(own, name, nextSub);
  }

  const instOpts = ["전체", ...childInstitutions];
  const showSubs = inst !== "전체" && childSubs.length > 1;

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
                  onClick={() => selectInst(name)}
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
        {showSubs ? (
          <div className="mt-2 border-l-2 border-line pl-3">
            <p className="mb-1.5 text-[11px] font-semibold text-muted">
              {inst} · 계좌
            </p>
            <div className="flex flex-wrap gap-1.5">
              {[{ key: "전체", label: "전체" }, ...childSubs].map((s) => {
                const active = sub === s.key;
                return (
                  <button
                    key={s.key}
                    type="button"
                    disabled={pending}
                    aria-pressed={active}
                    onClick={() => navigate(own, inst, s.key)}
                    className={`min-h-9 rounded-lg px-3 py-2 text-xs font-bold transition disabled:cursor-wait ${
                      active
                        ? "bg-brand text-white"
                        : "bg-surface text-muted ring-1 ring-line"
                    }`}
                  >
                    {s.label}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>
      {inst !== "전체" ? (
        <p className="text-[11px] text-muted">
          계좌 필터 중에는 기타자산·부채가 순자산에서 제외됩니다.
        </p>
      ) : null}
    </div>
  );
}
