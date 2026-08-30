// OCR parse: storage path → Gemini Vision → ocr_staging insert
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import {
  corsHeaders,
  json,
  requireCoupleUser,
  geminiGenerate,
  extractJsonObject,
  bytesToBase64,
  serviceClient,
} from "../_shared/gemini.ts";
import { correctOcrParsed } from "../_shared/krTicker.ts";

const OCR_PROMPT = `You are a financial OCR assistant for a Korean couple's wealth tracker (부자뚱).
Extract holdings, trades, dividends, and/or debt (loan) info from this screenshot.

Return ONLY valid JSON (no markdown) with this schema:
{
  "account_hint": "institution name if visible",
  "trades": [{"trade_date":"YYYY-MM-DD","ticker":"string","name":"string","trade_type":"buy"|"sell","price":number,"quantity":number,"fee":number,"currency":"KRW"|"USD","reason":"string"}],
  "dividends": [{"pay_date":"YYYY-MM-DD","ticker":"string","name":"string","amount":number,"currency":"KRW"|"USD","memo":"string"}],
  "holdings_snapshot": [{"ticker":"string","name":"string","quantity":number,"avg_price":number,"last_price":number,"currency":"KRW"|"USD"}],
  "debts": [{"lender":"string","debt_kind":"mortgage"|"credit"|"card"|"student"|"jeonse"|"other","balance":number,"original_principal":number|null,"interest_rate":number|null,"due_date":"YYYY-MM-DD"|null,"memo":"string"}],
  "debt_payments": [{"pay_date":"YYYY-MM-DD","lender":"string","amount":number,"interest_portion":number|null,"principal_portion":number|null,"balance_after":number|null,"rate":number|null,"memo":"string"}]
}

Rules:
- Prefer holdings_snapshot for balances, trades for order history, dividends for 배당, debts/debt_payments for loans.
- Numbers must be plain JSON numbers. Korean stocks: 6-digit tickers. Always include both ticker and name.
- last_price is 현재가/평가단가 when visible. avg_price is 평균단가.
- Do not invent a 6-digit ticker. If the code is unreadable, omit ticker and keep the Korean name.
- If unreadable return empty arrays and "error":"unreadable".`;

const DOC_HINTS: Record<string, string> = {
  holdings: "Focus on holdings_snapshot. Every row needs ticker and name.",
  trades: "Focus on trades (buy/sell). Every trade needs ticker and name.",
  dividends: "Focus on dividends. Every row needs ticker and name.",
  debt: "Focus on debts and debt_payments (대출/원리금).",
  auto: "Detect holdings/trades/dividends/debt and fill matching arrays.",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  try {
    if (req.method !== "POST") return json({ ok: false, error: "POST only" }, 405);

    const { supabase, user } = await requireCoupleUser(req);
    const body = await req.json();
    const imagePath = String(body.image_path || "").trim();
    const accountId = body.account_id ? String(body.account_id) : null;
    const docType = String(body.doc_type || "auto");
    const mimeType = String(body.mime_type || "image/png");

    if (!imagePath) return json({ ok: false, error: "image_path required" }, 400);
    if (!imagePath.startsWith(`${user.id}/`)) {
      return json({ ok: false, error: "image_path must be under your user folder" }, 403);
    }

    // Download via service role (private bucket)
    const admin = serviceClient();
    const { data: file, error: dlErr } = await admin.storage
      .from("ocr-screenshots")
      .download(imagePath);
    if (dlErr || !file) {
      return json({ ok: false, error: dlErr?.message || "download failed" }, 400);
    }

    const bytes = new Uint8Array(await file.arrayBuffer());
    const b64 = bytesToBase64(bytes);
    const hint = DOC_HINTS[docType] || DOC_HINTS.auto;
    const prompt = `${OCR_PROMPT}\n\nDocument hint: ${hint}\n`;

    let parsed: Record<string, unknown>;
    let status = "pending";
    let errorMsg: string | null = null;
    try {
      const text = await geminiGenerate({
        temperature: 0.1,
        parts: [
          { text: prompt },
          { inline_data: { mime_type: mimeType, data: b64 } },
        ],
      });
      parsed = extractJsonObject(text);
    } catch (e) {
      status = "failed";
      errorMsg = e instanceof Error ? e.message : "OCR failed";
      parsed = {
        trades: [],
        dividends: [],
        holdings_snapshot: [],
        debts: [],
        debt_payments: [],
        error: "unreadable",
      };
    }

    for (const key of [
      "trades",
      "dividends",
      "holdings_snapshot",
      "debts",
      "debt_payments",
    ]) {
      if (!Array.isArray(parsed[key])) parsed[key] = [];
    }
    if (accountId) parsed.account_id = accountId;
    parsed.doc_type = docType;
    if (status !== "failed") {
      parsed = await correctOcrParsed(parsed);
    }

    const { data: row, error: insErr } = await supabase
      .from("ocr_staging")
      .insert({
        uploaded_by: user.id,
        image_url: imagePath,
        parsed_json: parsed,
        status,
      })
      .select("id,status,image_url,parsed_json")
      .single();

    if (insErr) return json({ ok: false, error: insErr.message }, 400);

    return json({
      ok: true,
      staging_id: row.id,
      status: row.status,
      image_url: row.image_url,
      parsed_json: row.parsed_json,
      error_msg: errorMsg,
    });
  } catch (e) {
    if (e instanceof Response) return e;
    return json(
      { ok: false, error: e instanceof Error ? e.message : "unknown" },
      500
    );
  }
});
