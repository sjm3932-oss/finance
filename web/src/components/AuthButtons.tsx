"use client";

import { createClient } from "@/lib/supabase/client";

export function GoogleLoginButton() {
  async function onLogin() {
    const supabase = createClient();
    const origin = window.location.origin;
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${origin}/auth/callback`,
      },
    });
  }

  return (
    <button
      type="button"
      onClick={onLogin}
      className="inline-flex w-full items-center justify-center rounded-2xl bg-brand px-4 py-3.5 text-base font-bold text-white transition hover:bg-brand-dark"
    >
      Google로 로그인
    </button>
  );
}

export function LogoutButton() {
  async function onLogout() {
    const supabase = createClient();
    await supabase.auth.signOut();
    window.location.href = "/login";
  }

  return (
    <button
      type="button"
      onClick={onLogout}
      className="rounded-full border border-line bg-surface px-3 py-1.5 text-xs font-semibold text-muted"
    >
      로그아웃
    </button>
  );
}
