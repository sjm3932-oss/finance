import { redirect } from "next/navigation";
import { BottomNav } from "@/components/BottomNav";
import { RecordFab } from "@/components/RecordFab";
import { LogoutButton } from "@/components/AuthButtons";
import { displayNameFromUser, isEmailAllowed } from "@/lib/auth";
import { createClient } from "@/lib/supabase/server";

async function ensureProfile(
  supabase: Awaited<ReturnType<typeof createClient>>,
  user: { id: string; email?: string | null; user_metadata?: Record<string, unknown> | null }
) {
  const displayName = displayNameFromUser(user);
  // Prefer RPC used by Streamlit if present; fall back to upsert.
  const { error: rpcError } = await supabase.rpc("register_couple_user", {
    p_display_name: displayName,
  });
  if (!rpcError) return;

  await supabase.from("users").upsert(
    {
      id: user.id,
      email: (user.email || "").toLowerCase(),
      display_name: displayName,
    },
    { onConflict: "id" }
  );
}

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");
  if (!isEmailAllowed(user.email)) redirect("/denied");

  await ensureProfile(supabase, user);
  const name = displayNameFromUser(user);

  return (
    <div className="mx-auto min-h-dvh max-w-lg">
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-canvas/95 px-4 py-3 backdrop-blur">
        <div>
          <p className="text-[11px] font-bold tracking-wide text-brand">부자뚱</p>
          <p className="text-sm font-semibold text-ink">{name}</p>
        </div>
        <LogoutButton />
      </header>
      <div className="safe-pb px-4 pt-4">{children}</div>
      <RecordFab />
      <BottomNav />
    </div>
  );
}
