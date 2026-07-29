"use client";

import { usePathname, useRouter } from "next/navigation";
import { LogoutButton } from "@/components/AuthButtons";
import { NavBusyBar, markNavStart } from "@/components/navBusy";

export function AppHeader({ name }: { name: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const showBack = pathname !== "/";

  function goBack() {
    markNavStart();
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
      return;
    }
    router.push("/");
  }

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-canvas/95 backdrop-blur">
      <div className="relative flex items-center justify-between px-3 py-3">
        <div className="flex min-w-0 items-center gap-1.5">
          {showBack ? (
            <button
              type="button"
              onClick={goBack}
              aria-label="이전 화면"
              className="-ml-1 flex h-10 w-10 shrink-0 touch-manipulation items-center justify-center rounded-full text-ink transition-transform active:scale-90 active:bg-line/60"
            >
              <svg
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                aria-hidden
              >
                <path
                  d="M15 6l-6 6 6 6"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          ) : null}
          <div className="min-w-0">
            <p className="text-[11px] font-bold tracking-wide text-brand">
              부자뚱
            </p>
            <p className="truncate text-sm font-semibold text-ink">{name}</p>
          </div>
        </div>
        <LogoutButton />
        <NavBusyBar />
      </div>
    </header>
  );
}
