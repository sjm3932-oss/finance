"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { markNavStart } from "@/components/navBusy";

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
      prefetch
      onClick={() => markNavStart()}
      className="fixed bottom-[calc(5.25rem+env(safe-area-inset-bottom))] right-4 z-40 flex h-12 touch-manipulation items-center rounded-full bg-brand px-4 text-sm font-extrabold text-white shadow-lg shadow-brand/30 transition-transform active:scale-90"
      aria-label="AI 채팅"
    >
      AI
    </Link>
  );
}
