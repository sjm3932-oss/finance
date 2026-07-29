"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

const EDGE_PX = 28;
const SWIPE_MIN_X = 72;
const SWIPE_MAX_Y = 56;

export function AppMain({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const chat = pathname.startsWith("/chat");
  const startRef = useRef<{ x: number; y: number; edge: boolean } | null>(
    null
  );

  useEffect(() => {
    if (pathname === "/") return;

    function onStart(e: TouchEvent) {
      if (e.touches.length !== 1) return;
      const t = e.touches[0];
      startRef.current = {
        x: t.clientX,
        y: t.clientY,
        edge: t.clientX <= EDGE_PX,
      };
    }

    function onEnd(e: TouchEvent) {
      const start = startRef.current;
      startRef.current = null;
      if (!start?.edge || e.changedTouches.length !== 1) return;
      const t = e.changedTouches[0];
      const dx = t.clientX - start.x;
      const dy = Math.abs(t.clientY - start.y);
      if (dx >= SWIPE_MIN_X && dy <= SWIPE_MAX_Y) {
        if (typeof window !== "undefined" && window.history.length > 1) {
          router.back();
        } else {
          router.push("/");
        }
      }
    }

    function onCancel() {
      startRef.current = null;
    }

    document.addEventListener("touchstart", onStart, { passive: true });
    document.addEventListener("touchend", onEnd, { passive: true });
    document.addEventListener("touchcancel", onCancel, { passive: true });
    return () => {
      document.removeEventListener("touchstart", onStart);
      document.removeEventListener("touchend", onEnd);
      document.removeEventListener("touchcancel", onCancel);
    };
  }, [pathname, router]);

  return (
    <div className={`px-4 pt-4 ${chat ? "pb-2" : "safe-pb"}`}>{children}</div>
  );
}
