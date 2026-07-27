export function allowedEmails(): Set<string> {
  const raw =
    process.env.ALLOWED_EMAILS ||
    process.env.NEXT_PUBLIC_ALLOWED_EMAILS ||
    "";
  return new Set(
    raw
      .split(",")
      .map((e) => e.trim().toLowerCase())
      .filter(Boolean)
  );
}

export function isEmailAllowed(email: string | null | undefined): boolean {
  if (!email) return false;
  const allow = allowedEmails();
  if (allow.size === 0) return false;
  return allow.has(email.trim().toLowerCase());
}

export function displayNameFromUser(user: {
  email?: string | null;
  user_metadata?: Record<string, unknown> | null;
}): string {
  const meta = user.user_metadata || {};
  for (const key of ["full_name", "name", "display_name"]) {
    const v = meta[key];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  return (user.email || "회원").split("@")[0];
}
