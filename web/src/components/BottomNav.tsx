"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ITEMS = [
  { href: "/", label: "홈" },
  { href: "/holdings", label: "보유" },
  { href: "/pnl", label: "손익" },
  { href: "/flows", label: "거래" },
  { href: "/more", label: "더보기" },
] as const;

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-surface/95 backdrop-blur-md">
      <div
        className="mx-auto grid max-w-lg grid-cols-5 px-0.5 pt-2"
        style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}
      >
        {ITEMS.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
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
