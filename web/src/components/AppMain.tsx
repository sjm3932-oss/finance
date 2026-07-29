"use client";

import { usePathname } from "next/navigation";

export function AppMain({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const chat = pathname.startsWith("/chat");
  return (
    <div className={`px-4 pt-4 ${chat ? "pb-2" : "safe-pb"}`}>{children}</div>
  );
}
