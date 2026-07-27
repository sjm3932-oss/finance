import Link from "next/link";
import { LogoutButton } from "@/components/AuthButtons";

export default function DeniedPage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-lg flex-col justify-center px-5">
      <div className="rounded-3xl border border-line bg-surface p-7 shadow-soft">
        <h1 className="text-2xl font-extrabold tracking-tight">접근 거부</h1>
        <p className="mt-3 text-sm text-muted">
          이 Google 계정은 allow-list에 없습니다. 부부 계정만 사용할 수 있습니다.
        </p>
        <div className="mt-6 flex items-center gap-3">
          <LogoutButton />
          <Link href="/login" className="text-sm font-semibold text-brand">
            로그인으로
          </Link>
        </div>
      </div>
    </main>
  );
}
