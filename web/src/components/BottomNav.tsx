"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const MAIN_ITEMS = [
  { href: "/", label: "홈" },
  { href: "/holdings", label: "보유" },
  { href: "/pnl", label: "손익" },
  { href: "/flows", label: "거래" },
  { href: "/more", label: "더보기", opensMore: true },
] as const;

/** Toss-style 2nd-level strip for 더보기 only. */
const MORE_ITEMS = [
  {
    href: "/more",
    label: "전체",
    match: (p: string) => p === "/more",
    icon: IconGrid,
  },
  {
    href: "/record",
    label: "기록",
    match: (p: string) => p.startsWith("/record"),
    icon: IconEdit,
  },
  {
    href: "/ocr",
    label: "OCR",
    match: (p: string) => p.startsWith("/ocr"),
    icon: IconCamera,
  },
  {
    href: "/more/net-worth",
    label: "순자산",
    match: (p: string) =>
      p.startsWith("/more/net-worth") ||
      p.startsWith("/more/other-assets") ||
      p.startsWith("/more/debts"),
    icon: IconPie,
  },
  {
    href: "/more/watchlist",
    label: "관심",
    match: (p: string) => p.startsWith("/more/watchlist"),
    icon: IconHeart,
  },
  {
    href: "/more/tax",
    label: "세금",
    match: (p: string) => p.startsWith("/more/tax"),
    icon: IconTax,
  },
] as const;

function isMoreSection(pathname: string) {
  return (
    pathname === "/more" ||
    pathname.startsWith("/more/") ||
    pathname.startsWith("/record") ||
    pathname.startsWith("/ocr")
  );
}

export function BottomNav() {
  const pathname = usePathname();
  const router = useRouter();
  /** After ←, show main tabs even if still on a more-section URL briefly. */
  const [forceMain, setForceMain] = useState(false);

  useEffect(() => {
    if (!isMoreSection(pathname)) setForceMain(false);
  }, [pathname]);

  const showMoreMenu = isMoreSection(pathname) && !forceMain;

  if (showMoreMenu) {
    return (
      <nav
        className="fixed inset-x-0 bottom-0 z-40 px-3"
        style={{ paddingBottom: "max(0.65rem, env(safe-area-inset-bottom))" }}
        aria-label="더보기 하위 메뉴"
      >
        <div className="mx-auto flex max-w-lg items-center gap-1 rounded-full border border-line bg-surface px-1.5 py-1.5 shadow-[0_8px_28px_rgba(26,26,26,0.12)]">
          <button
            type="button"
            onClick={() => {
              setForceMain(true);
              router.push("/");
            }}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-canvas text-ink active:scale-95"
            aria-label="주메뉴로 돌아가기"
          >
            <IconBack />
          </button>
          <div className="flex min-w-0 flex-1 items-stretch justify-between px-0.5">
            {MORE_ITEMS.map((item) => {
              const active = item.match(pathname);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setForceMain(false)}
                  className={`flex min-w-0 flex-1 flex-col items-center justify-center gap-0.5 rounded-2xl py-1 transition ${
                    active ? "text-brand" : "text-muted"
                  }`}
                >
                  <Icon active={active} />
                  <span className="truncate text-[10px] font-bold tracking-tight">
                    {item.label}
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      </nav>
    );
  }

  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-surface/95 backdrop-blur-md">
      <div
        className="mx-auto grid max-w-lg grid-cols-5 px-0.5 pt-2"
        style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}
      >
        {MAIN_ITEMS.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : item.href === "/more"
                ? false
                : pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => {
                if ("opensMore" in item && item.opensMore) setForceMain(false);
              }}
              className={`flex flex-col items-center justify-center rounded-xl py-2 text-[13px] font-bold tracking-tight transition ${
                active ? "text-brand" : "text-muted"
              }`}
            >
              <span
                className={`mb-1 h-1 w-5 rounded-full ${
                  active ? "bg-brand" : "bg-transparent"
                }`}
              />
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

function IconBack() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M15 6L9 12l6 6"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconGrid({ active }: { active?: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="4" y="4" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8} />
      <rect x="13" y="4" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8} />
      <rect x="4" y="13" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8} />
      <rect x="13" y="13" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8} />
    </svg>
  );
}

function IconEdit({ active }: { active?: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17v3z"
        stroke="currentColor"
        strokeWidth={active ? 2.2 : 1.8}
        strokeLinejoin="round"
      />
      <path
        d="M13.5 6.5l3 3"
        stroke="currentColor"
        strokeWidth={active ? 2.2 : 1.8}
        strokeLinecap="round"
      />
    </svg>
  );
}

function IconCamera({ active }: { active?: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M4 8.5A2.5 2.5 0 0 1 6.5 6h2l1.2-1.6A1.5 1.5 0 0 1 10.9 4h2.2a1.5 1.5 0 0 1 1.2.6L15.5 6h2A2.5 2.5 0 0 1 20 8.5v9A2.5 2.5 0 0 1 17.5 20h-11A2.5 2.5 0 0 1 4 17.5v-9z"
        stroke="currentColor"
        strokeWidth={active ? 2.2 : 1.8}
      />
      <circle cx="12" cy="13" r="3.2" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8} />
    </svg>
  );
}

function IconPie({ active }: { active?: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 4a8 8 0 1 0 8 8h-8V4z"
        stroke="currentColor"
        strokeWidth={active ? 2.2 : 1.8}
        strokeLinejoin="round"
      />
      <path
        d="M14 4.3A8 8 0 0 1 19.7 10H14V4.3z"
        stroke="currentColor"
        strokeWidth={active ? 2.2 : 1.8}
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconHeart({ active }: { active?: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 20s-7-4.4-7-9.2A3.8 3.8 0 0 1 12 7.5a3.8 3.8 0 0 1 7 3.3C19 15.6 12 20 12 20z"
        stroke="currentColor"
        strokeWidth={active ? 2.2 : 1.8}
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconTax({ active }: { active?: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect
        x="5"
        y="3.5"
        width="14"
        height="17"
        rx="2"
        stroke="currentColor"
        strokeWidth={active ? 2.2 : 1.8}
      />
      <path
        d="M8 8h8M8 12h8M8 16h5"
        stroke="currentColor"
        strokeWidth={active ? 2.2 : 1.8}
        strokeLinecap="round"
      />
    </svg>
  );
}
