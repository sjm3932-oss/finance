import { redirect } from "next/navigation";
import { GoogleLoginButton } from "@/components/AuthButtons";
import { createClient } from "@/lib/supabase/server";

export default async function LoginPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (user) redirect("/");

  return (
    <main className="mx-auto flex min-h-dvh max-w-lg flex-col justify-center px-5 py-10">
      <div className="rounded-3xl border border-line bg-surface p-7 shadow-soft">
        <p className="text-sm font-bold tracking-wide text-brand">부자뚱</p>
        <h1 className="mt-2 text-3xl font-extrabold tracking-tight">
          정명지수 공동 자산
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-muted">
          로그인 후 순자산·보유를 보고, 더보기 → 기록하기·OCR로 입력합니다.
        </p>
        <div className="mt-8">
          <GoogleLoginButton />
        </div>
        <p className="mt-4 text-center text-xs text-muted">
          allow-list 이메일의 Google 계정만 접근할 수 있습니다.
        </p>
      </div>
    </main>
  );
}
