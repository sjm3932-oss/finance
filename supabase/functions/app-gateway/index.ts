// Stable public gateway: always 302 to the live Streamlit URL from app_runtime.
// OAuth PKCE callbacks arrive as ?code=... (fragments are not required).
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: cors });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
    const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
    const anonKey = Deno.env.get("SUPABASE_ANON_KEY") ?? "";
    const key = serviceKey || anonKey;
    if (!supabaseUrl || !key) {
      return new Response("Missing Supabase env", { status: 500, headers: cors });
    }

    const sb = createClient(supabaseUrl, key);
    const { data, error } = await sb
      .from("app_runtime")
      .select("public_url")
      .eq("id", 1)
      .maybeSingle();

    if (error || !data?.public_url) {
      return new Response(
        `App URL not registered yet (${error?.message ?? "empty"})`,
        { status: 503, headers: { ...cors, "Content-Type": "text/plain; charset=utf-8" } },
      );
    }

    const appBase = String(data.public_url).replace(/\/$/, "");
    const incoming = new URL(req.url);
    const dest = new URL(appBase);

    // Forward OAuth / session query params to Streamlit.
    for (const [k, v] of incoming.searchParams.entries()) {
      dest.searchParams.set(k, v);
    }

    return new Response(null, {
      status: 302,
      headers: {
        ...cors,
        Location: dest.toString(),
        "Cache-Control": "no-store",
      },
    });
  } catch (err) {
    return new Response(`Gateway error: ${err}`, {
      status: 500,
      headers: { ...cors, "Content-Type": "text/plain; charset=utf-8" },
    });
  }
});
