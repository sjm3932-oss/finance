// Nightly logical backup: dump public tables to Storage bucket `backups`, keep 7 days
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const TABLES = [
  "users",
  "accounts",
  "holdings",
  "market_prices",
  "trades",
  "cash_flows",
  "debts",
  "daily_snapshots",
  "market_index_snapshots",
  "tax_records",
  "ai_chat_logs",
  "ocr_staging",
  "push_subscriptions",
  "allowed_emails",
  "app_settings",
];

Deno.serve(async (_req) => {
  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    const dump: Record<string, unknown> = {
      exported_at: new Date().toISOString(),
      tables: {},
    };

    for (const table of TABLES) {
      const { data, error } = await supabase.from(table).select("*");
      if (error) {
        dump.tables[table] = { error: error.message };
      } else {
        dump.tables[table] = data;
      }
    }

    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const path = `logical/${stamp}.json`;
    const body = JSON.stringify(dump);
    const { error: upErr } = await supabase.storage
      .from("backups")
      .upload(path, new Blob([body], { type: "application/json" }), {
        contentType: "application/json",
        upsert: true,
      });
    if (upErr) throw upErr;

    // Retention: delete files older than 7 days
    const { data: files } = await supabase.storage.from("backups").list("logical", {
      limit: 100,
    });
    const cutoff = Date.now() - 7 * 24 * 3600 * 1000;
    const removed: string[] = [];
    for (const f of files ?? []) {
      const updated = f.updated_at ? Date.parse(f.updated_at) : 0;
      if (updated && updated < cutoff) {
        const full = `logical/${f.name}`;
        await supabase.storage.from("backups").remove([full]);
        removed.push(full);
      }
    }

    return Response.json({
      ok: true,
      path,
      bytes: body.length,
      removed,
    });
  } catch (e) {
    return Response.json({ ok: false, error: String(e) }, { status: 500 });
  }
});
