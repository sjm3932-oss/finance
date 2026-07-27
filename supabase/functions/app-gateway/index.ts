// Production gateway: always send users to the fixed Streamlit Cloud app.
// Temporary tunnels (Pinggy/Cloudflare) are no longer used.
const cors: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Cache-Control": "no-store",
};

const PRODUCTION_APP_URL = (
  Deno.env.get("PRODUCTION_APP_URL") ||
  "https://richddoong.streamlit.app"
).replace(/\/$/, "");

Deno.serve((req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

  const incoming = new URL(req.url);
  const dest = new URL(PRODUCTION_APP_URL);
  for (const [k, v] of incoming.searchParams.entries()) {
    dest.searchParams.set(k, v);
  }

  return new Response(null, {
    status: 302,
    headers: { ...cors, Location: dest.toString() },
  });
});
