"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Floating write CTA — commercial apps keep primary write one tap away. */
export function RecordFab() {
  const pathname = usePathname();
  if (pathname.startsWith("/record") || pathname.startsWith("/login")) {
    return null;
  }

  return (
    <Link
      href="/record"
      className="fixed bottom-[calc(4.75rem+env(safe-area-inset-bottom))] right-4 z-40 flex h-12 items-center rounded-full bg-brand px-4 text-sm font-extrabold text-white shadow-lg shadow-brand/30 active:scale-95"
      aria-label="기록하기"
    >
      + 기록
    </Link>
  );
}
