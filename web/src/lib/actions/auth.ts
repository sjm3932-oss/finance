"use server";

import { isEmailAllowed } from "@/lib/auth";
import { createClient } from "@/lib/supabase/server";

export async function requireAllowedUser() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) throw new Error("로그인이 필요합니다.");
  if (!isEmailAllowed(user.email)) {
    throw new Error("허용되지 않은 계정입니다.");
  }
  return { supabase, user };
}
