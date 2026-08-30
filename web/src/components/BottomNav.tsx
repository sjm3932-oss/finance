"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  useEffect,
  useState,
  type ComponentType,
  type ReactNode,
} from "react";
import { markNavStart } from "@/components/navBusy";

const PREFETCH_HREFS = [
  "/",
  "/holdings",
  "/pnl",
  "/flows",
  "/more",
  "/record",
  "/ocr",
  "/more/net-worth",
  "/more/tax",
  "/more/toss",
  "/chat",
] as const;

type IconProps = { active?: boolean };

const MAIN_ITEMS: {
  href: string;
  label: string;
  opensMore?: boolean;
  match: (p: string) => boolean;
  icon: ComponentType<IconProps>;
}[] = [
  {
    href: "/",
    label: "홈",
    match: (p) => p === "/",
    icon: IconHome,
  },
  {
    href: "/holdings",
    label: "보유",
    match: (p) => p.startsWith("/holdings"),
    icon: IconHoldings,
  },
  {
    href: "/pnl",
    label: "손익",
    match: (p) => p.startsWith("/pnl"),
    icon: IconPnl,
  },
  {
    href: "/flows",
    label: "거래",
    match: (p) => p.startsWith("/flows"),
    icon: IconFlows,
  },
  {
    href: "/more",
    label: "더보기",
    opensMore: true,
    match: () => false,
    icon: IconMenu,
  },
];

/** Toss-style 2nd-level strip for 더보기 only. */
const MORE_ITEMS: {
  href: string;
  label: string;
  match: (p: string) => boolean;
  icon: ComponentType<IconProps>;
}[] = [
  {
    href: "/more",
    label: "전체",
    match: (p) => p === "/more",
    icon: IconGrid,
  },
  {
    href: "/more/toss",
    label: "토스",
    match: (p) => p.startsWith("/more/toss"),
    icon: IconSync,
  },
  {
    href: "/record",
    label: "기록",
    match: (p) => p.startsWith("/record"),
    icon: IconEdit,
  },
  {
    href: "/ocr",
    label: "OCR",
    match: (p) => p.startsWith("/ocr"),
    icon: IconCamera,
  },
  {
    href: "/more/net-worth",
    label: "순자산",
    match: (p) =>
      p.startsWith("/more/net-worth") ||
      p.startsWith("/more/other-assets") ||
      p.startsWith("/more/debts"),
    icon: IconPie,
  },
  {
    href: "/more/tax",
    label: "세금",
    match: (p) => p.startsWith("/more/tax"),
    icon: IconTax,
  },
];

function isMoreSection(pathname: string) {
  return (
    pathname === "/more" ||
    pathname.startsWith("/more/") ||
    pathname.startsWith("/record") ||
    pathname.startsWith("/ocr")
  );
}

function PillShell({
  label,
  leading,
  children,
}: {
  label: string;
  leading?: ReactNode;
  children: ReactNode;
}) {
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 px-3"
      style={{ paddingBottom: "max(0.65rem, env(safe-area-inset-bottom))" }}
      aria-label={label}
    >
      <div className="mx-auto flex max-w-lg items-center gap-1 rounded-full border border-line bg-surface px-1.5 py-1.5 shadow-[0_8px_28px_rgba(26,26,26,0.12)]">
        {leading}
        <div className="flex min-w-0 flex-1 items-stretch justify-between px-0.5">
          {children}
        </div>
      </div>
    </nav>
  );
}

function NavItem({
  href,
  label,
  active,
  pressed,
  icon: Icon,
  onClick,
}: {
  href: string;
  label: string;
  active: boolean;
  pressed?: boolean;
  icon: ComponentType<IconProps>;
  onClick?: () => void;
}) {
  const lit = active || !!pressed;
  return (
    <Link
      href={href}
      prefetch
      onClick={() => {
        markNavStart();
        onClick?.();
      }}
      className={`flex min-w-0 flex-1 touch-manipulation flex-col items-center justify-center gap-0.5 rounded-2xl py-1 transition-transform active:scale-90 ${
        lit ? "text-brand" : "text-muted"
      } ${pressed && !active ? "opacity-90" : ""}`}
    >
      <Icon active={lit} />
      <span className="truncate text-[10px] font-bold tracking-tight">{label}</span>
    </Link>
  );
}

export function BottomNav() {
  const pathname = usePathname();
  const router = useRouter();
  /** After ←, show main tabs even if still on a more-section URL briefly. */
  const [forceMain, setForceMain] = useState(false);
  const [pressedHref, setPressedHref] = useState<string | null>(null);

  useEffect(() => {
    if (!isMoreSection(pathname)) setForceMain(false);
    setPressedHref(null);
  }, [pathname]);

  useEffect(() => {
    for (const href of PREFETCH_HREFS) {
      router.prefetch(href);
    }
  }, [router]);

  if (pathname.startsWith("/chat") || pathname.startsWith("/login")) {
    return null;
  }

  const showMoreMenu = isMoreSection(pathname) && !forceMain;

  if (showMoreMenu) {
    return (
      <PillShell
        label="더보기 하위 메뉴"
        leading={
          <button
            type="button"
            onClick={() => {
              markNavStart();
              setForceMain(true);
              router.push("/");
            }}
            className="flex h-10 w-10 shrink-0 touch-manipulation items-center justify-center rounded-full bg-canvas text-ink transition-transform active:scale-90"
            aria-label="주메뉴로 돌아가기"
          >
            <IconBack />
          </button>
        }
      >
        {MORE_ITEMS.map((item) => (
          <NavItem
            key={item.href}
            href={item.href}
            label={item.label}
            active={item.match(pathname)}
            pressed={pressedHref === item.href}
            icon={item.icon}
            onClick={() => {
              setPressedHref(item.href);
              setForceMain(false);
            }}
          />
        ))}
      </PillShell>
    );
  }

  return (
    <PillShell label="주메뉴">
      {MAIN_ITEMS.map((item) => (
        <NavItem
          key={item.href}
          href={item.href}
          label={item.label}
          active={item.match(pathname)}
          pressed={pressedHref === item.href}
          icon={item.icon}
          onClick={() => {
            setPressedHref(item.href);
            if (item.opensMore) setForceMain(false);
          }}
        />
      ))}
    </PillShell>
  );
}

function stroke(active?: boolean) {
  return active ? 2.2 : 1.8;
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

function IconHome({ active }: IconProps) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5.5v-6h-3v6H5a1 1 0 0 1-1-1v-9.5z"
        stroke="currentColor"
        strokeWidth={stroke(active)}
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconHoldings({ active }: IconProps) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect
        x="3.5"
        y="7"
        width="17"
        height="12"
        rx="2"
        stroke="currentColor"
        strokeWidth={stroke(active)}
      />
      <path
        d="M8 7V5.5A1.5 1.5 0 0 1 9.5 4h5A1.5 1.5 0 0 1 16 5.5V7"
        stroke="currentColor"
        strokeWidth={stroke(active)}
      />
      <path
        d="M3.5 12h17"
        stroke="currentColor"
        strokeWidth={stroke(active)}
        strokeLinecap="round"
      />
    </svg>
  );
}

function IconPnl({ active }: IconProps) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M4 16.5 9 11l3.5 3.5L20 7"
        stroke="currentColor"
        strokeWidth={stroke(active)}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M15 7h5v5"
        stroke="currentColor"
        strokeWidth={stroke(active)}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconFlows({ active }: IconProps) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M7 7h11l-2.5-2.5M18 17H7l2.5 2.5"
        stroke="currentColor"
        strokeWidth={stroke(active)}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M18 7v4M6 13v4"
        stroke="currentColor"
        strokeWidth={stroke(active)}
        strokeLinecap="round"
      />
    </svg>
  );
}

function IconMenu({ active }: IconProps) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M5 7h14M5 12h14M5 17h14"
        stroke="currentColor"
        strokeWidth={stroke(active)}
        strokeLinecap="round"
      />
    </svg>
  );
}

function IconGrid({ active }: IconProps) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="4" y="4" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth={stroke(active)} />
      <rect x="13" y="4" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth={stroke(active)} />
      <rect x="4" y="13" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth={stroke(active)} />
      <rect x="13" y="13" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth={stroke(active)} />
    </svg>
  );
}

function IconSync({ active }: IconProps) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M4 12a8 8 0 0 1 13.5-5.8L20 8"
        stroke="currentColor"
        strokeWidth={stroke(active)}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M20 4v4h-4"
        stroke="currentColor"
        strokeWidth={stroke(active)}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M20 12a8 8 0 0 1-13.5 5.8L4 16"
        stroke="currentColor"
        strokeWidth={stroke(active)}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M4 20v-4h4"
        stroke="currentColor"
        strokeWidth={stroke(active)}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconEdit({ active }: IconProps) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17v3z"
        stroke="currentColor"
        strokeWidth={stroke(active)}
        strokeLinejoin="round"
      />
      <path
        d="M13.5 6.5l3 3"
        stroke="currentColor"
        strokeWidth={stroke(active)}
        strokeLinecap="round"
      />
    </svg>
  );
}

function IconCamera({ active }: IconProps) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M4 8.5A2.5 2.5 0 0 1 6.5 6h2l1.2-1.6A1.5 1.5 0 0 1 10.9 4h2.2a1.5 1.5 0 0 1 1.2.6L15.5 6h2A2.5 2.5 0 0 1 20 8.5v9A2.5 2.5 0 0 1 17.5 20h-11A2.5 2.5 0 0 1 4 17.5v-9z"
        stroke="currentColor"
        strokeWidth={stroke(active)}
      />
      <circle cx="12" cy="13" r="3.2" stroke="currentColor" strokeWidth={stroke(active)} />
    </svg>
  );
}

function IconPie({ active }: IconProps) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 4a8 8 0 1 0 8 8h-8V4z"
        stroke="currentColor"
        strokeWidth={stroke(active)}
        strokeLinejoin="round"
      />
      <path
        d="M14 4.3A8 8 0 0 1 19.7 10H14V4.3z"
        stroke="currentColor"
        strokeWidth={stroke(active)}
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconTax({ active }: IconProps) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect
        x="5"
        y="3.5"
        width="14"
        height="17"
        rx="2"
        stroke="currentColor"
        strokeWidth={stroke(active)}
      />
      <path
        d="M8 8h8M8 12h8M8 16h5"
        stroke="currentColor"
        strokeWidth={stroke(active)}
        strokeLinecap="round"
      />
    </svg>
  );
}
