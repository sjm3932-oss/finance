// Shared helpers for Edge Functions
import { createClient, type SupabaseClient, type User } from "jsr:@supabase/supabase-js@2";

export const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

export function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

function anonKey(): string {
  const key = Deno.env.get("SUPABASE_ANON_KEY");
  if (!key) throw new Error("SUPABASE_ANON_KEY missing");
  return key;
}

export function userClient(req: Request): SupabaseClient {
  const auth = req.headers.get("Authorization") ?? "";
  return createClient(Deno.env.get("SUPABASE_URL")!, anonKey(), {
    global: { headers: { Authorization: auth } },
    auth: { persistSession: false },
  });
}

export function serviceClient(): SupabaseClient {
  return createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
  );
}

export async function requireUser(req: Request) {
  const supabase = userClient(req);
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();
  if (error || !user) {
    throw json({ ok: false, error: "unauthorized" }, 401);
  }
  return { supabase, user };
}

/** JWT + DB allow-list (allowed_emails). Blocks non-couple callers before service-role reads. */
export async function requireCoupleUser(req: Request): Promise<{
  supabase: SupabaseClient;
  user: User;
}> {
  const { supabase, user } = await requireUser(req);
  const email = (user.email || "").trim().toLowerCase();
  if (!email) {
    throw json({ ok: false, error: "forbidden: no email" }, 403);
  }

  const { data: allowed, error } = await supabase.rpc("email_is_allowed", {
    p_email: email,
  });
  if (error) {
    // Fallback: direct table read via service role (RPC missing / older DB)
    const admin = serviceClient();
    const { data: row } = await admin
      .from("allowed_emails")
      .select("email")
      .eq("email", email)
      .maybeSingle();
    if (!row) {
      throw json({ ok: false, error: "forbidden" }, 403);
    }
  } else if (!allowed) {
    throw json({ ok: false, error: "forbidden" }, 403);
  }

  return { supabase, user };
}

export async function geminiGenerate(opts: {
  parts: unknown[];
  temperature?: number;
  systemInstruction?: string;
}) {
  const apiKey = Deno.env.get("GEMINI_API_KEY");
  if (!apiKey) throw new Error("GEMINI_API_KEY missing in function secrets");
  const model = Deno.env.get("GEMINI_MODEL") ?? "gemini-2.5-flash";
  const url =
    `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;

  const body: Record<string, unknown> = {
    contents: [{ role: "user", parts: opts.parts }],
    generationConfig: { temperature: opts.temperature ?? 0.3 },
  };
  if (opts.systemInstruction) {
    body.systemInstruction = { parts: [{ text: opts.systemInstruction }] };
  }

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`Gemini ${res.status}: ${t.slice(0, 400)}`);
  }
  const data = await res.json();
  const text =
    data?.candidates?.[0]?.content?.parts
      ?.map((p: { text?: string }) => p.text ?? "")
      .join("") ?? "";
  if (!text) throw new Error("Empty Gemini response");
  return text.trim();
}

export function extractJsonObject(text: string): Record<string, unknown> {
  let t = text.trim();
  if (t.startsWith("```")) {
    t = t.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
  }
  try {
    const data = JSON.parse(t);
    if (data && typeof data === "object" && !Array.isArray(data)) return data;
  } catch {
    /* fall through */
  }
  const match = t.match(/\{[\s\S]*\}/);
  if (!match) throw new Error("Gemini response did not contain JSON");
  const data = JSON.parse(match[0]);
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new Error("Gemini JSON root must be an object");
  }
  return data;
}

export function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}
