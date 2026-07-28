"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Floating AI chat entry — record lives under 더보기. */
export function AiFab() {
  const pathname = usePathname();
  if (
    pathname.startsWith("/chat") ||
    pathname.startsWith("/login") ||
    pathname.startsWith("/denied")
  ) {
    return null;
  }

  return (
    <Link
      href="/chat"
      className="fixed bottom-[calc(4.75rem+env(safe-area-inset-bottom))] right-4 z-40 flex h-12 items-center rounded-full bg-brand px-4 text-sm font-extrabold text-white shadow-lg shadow-brand/30 active:scale-95"
      aria-label="AI 채팅"
    >
      AI
    </Link>
  );
}
