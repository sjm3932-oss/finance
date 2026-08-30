// Toss Securities holdings sync (no orders).
// Docs: https://developers.tossinvest.com/llms.txt
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import {
  corsHeaders,
  json,
  requireCoupleUser,
  serviceClient,
} from "../_shared/gemini.ts";

const TOSS_BASE = "https://openapi.tossinvest.com";
const INSTITUTION = "토스증권";

function toNumber(raw: unknown): number {
  if (raw == null || raw === "") return 0;
  const n = Number(String(raw).replace(/,/g, "").trim());
  return Number.isFinite(n) ? n : 0;
}

function normalizeTicker(symbol: string, marketCountry?: string): string {
  let t = String(symbol || "").trim().toUpperCase();
  if (t.endsWith(".KS") || t.endsWith(".KQ")) {
    const base = t.slice(0, -3);
    if (/^\d{6}$/.test(base)) return base;
  }
  if ((marketCountry || "").toUpperCase() === "KR" && /^\d{1,6}$/.test(t)) {
    return t.padStart(6, "0");
  }
  return t;
}

type Mapped = {
  ticker: string;
  name: string;
  quantity: number;
  avg_price: number;
  currency: "KRW" | "USD";
  last_price: number;
};

function mapHolding(item: Record<string, unknown>): Mapped | null {
  const symbol = String(item.symbol || "").trim();
  if (!symbol) return null;
  const qty = toNumber(item.quantity);
  if (qty <= 0) return null;
  let currency = String(item.currency || "KRW").toUpperCase();
  if (currency !== "KRW" && currency !== "USD") {
    currency = String(item.marketCountry || "").toUpperCase() === "US" ? "USD" : "KRW";
  }
  const ticker = normalizeTicker(symbol, String(item.marketCountry || ""));
  return {
    ticker,
    name: String(item.name || ticker).trim() || ticker,
    quantity: qty,
    avg_price: toNumber(item.averagePurchasePrice),
    currency: currency as "KRW" | "USD",
    last_price: toNumber(item.lastPrice),
  };
}

async function egressIp(): Promise<string | null> {
  for (const url of ["https://api.ipify.org?format=json", "https://ipv4.icanhazip.com"]) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(4000) });
      const text = (await res.text()).trim();
      if (url.includes("ipify")) {
        const ip = String((JSON.parse(text) as { ip?: string }).ip || "").trim();
        if (ip) return ip;
      } else if (text) {
        return text.split(/\s+/)[0];
      }
    } catch {
      /* try next */
    }
  }
  return null;
}

function isIpBlocked(status: number, payload: unknown): boolean {
  const p = payload as { error?: { code?: string } | string };
  const err = p?.error;
  const code = typeof err === "string" ? err : err?.code || "";
  return status === 403 || code === "edge-blocked" || code === "forbidden";
}

function humanize(status: number, payload: unknown, ip?: string | null): string {
  const p = payload as { error?: { code?: string; message?: string } | string; error_description?: string };
  const err = p?.error;
  const code = typeof err === "string" ? err : err?.code || "";
  const message = typeof err === "object" && err ? err.message || "" : p?.error_description || "";
  if (isIpBlocked(status, payload)) {
    const shown = ip ? ` ${ip}` : "";
    return `토스 Open API가 이 서버 IP를 막았습니다.${shown} Edge Function 출구 IP는 호출마다 바뀝니다. 하나를 등록해도 다음 동기화에서 또 막힐 수 있습니다.`;
  }
  if (status === 401 || code === "invalid-token" || code === "expired-token" || code === "invalid_client") {
    return "토스 인증 실패. TOSS_CLIENT_ID / TOSS_CLIENT_SECRET 을 Function secrets에 넣었는지 확인하세요.";
  }
  if (status === 429) return "토스 API 호출 한도를 넘었습니다. 잠시 후 다시 시도하세요.";
  if (message) return message;
  if (code) return `토스 API 오류 (${code})`;
  return `토스 API HTTP ${status}`;
}

async function tossRequest(
  method: string,
  path: string,
  opts: {
    token?: string;
    accountSeq?: number;
    query?: Record<string, string>;
    form?: Record<string, string>;
  } = {},
): Promise<{ status: number; payload: unknown }> {
  const url = new URL(TOSS_BASE + path);
  if (opts.query) {
    for (const [k, v] of Object.entries(opts.query)) url.searchParams.set(k, v);
  }
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: string | undefined;
  if (opts.form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    body = new URLSearchParams(opts.form).toString();
  }
  if (opts.token) headers.Authorization = `Bearer ${opts.token}`;
  if (opts.accountSeq != null) headers["X-Tossinvest-Account"] = String(opts.accountSeq);
  const res = await fetch(url, { method, headers, body });
  const text = await res.text();
  let payload: unknown = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = { raw: text.slice(0, 400) };
  }
  return { status: res.status, payload };
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  try {
    if (req.method === "GET") {
      const ip = await egressIp();
      return json({ ok: true, egress_ip: ip });
    }
    if (req.method !== "POST") return json({ ok: false, error: "POST only" }, 405);
    const { user } = await requireCoupleUser(req);

    let probe = false;
    try {
      const body = await req.clone().json();
      probe = !!(body && typeof body === "object" && (body as { probe?: boolean }).probe);
    } catch {
      /* empty body is a full sync */
    }
    if (probe) {
      const ip = await egressIp();
      return json({ ok: true, egress_ip: ip });
    }

    const clientId = Deno.env.get("TOSS_CLIENT_ID")?.trim();
    const clientSecret = Deno.env.get("TOSS_CLIENT_SECRET")?.trim();
    if (!clientId || !clientSecret) {
      return json({
        ok: false,
        error:
          "TOSS_CLIENT_ID / TOSS_CLIENT_SECRET 이 없습니다. supabase secrets set 후 functions deploy toss-sync.",
      }, 400);
    }

    const tok = await tossRequest("POST", "/oauth2/token", {
      form: {
        grant_type: "client_credentials",
        client_id: clientId,
        client_secret: clientSecret,
      },
    });
    const access = (tok.payload as { access_token?: string })?.access_token;
    if (tok.status !== 200 || !access) {
      const ip = isIpBlocked(tok.status, tok.payload) ? await egressIp() : null;
      return json(
        { ok: false, error: humanize(tok.status, tok.payload, ip), egress_ip: ip },
        isIpBlocked(tok.status, tok.payload) ? 403 : 400,
      );
    }

    const acc = await tossRequest("GET", "/api/v1/accounts", { token: access });
    if (acc.status !== 200) {
      const ip = isIpBlocked(acc.status, acc.payload) ? await egressIp() : null;
      return json(
        { ok: false, error: humanize(acc.status, acc.payload, ip), egress_ip: ip },
        isIpBlocked(acc.status, acc.payload) ? 403 : 400,
      );
    }
    const listed = ((acc.payload as { result?: Array<Record<string, unknown>> })?.result) || [];
    let brokerage = listed.filter((a) => a.accountType === "BROKERAGE" || a.accountType == null);
    if (!brokerage.length) brokerage = listed;
    if (!brokerage.length) {
      return json({ ok: false, error: "토스 계좌가 없습니다." }, 400);
    }

    const admin = serviceClient();
    const fx = await tossRequest("GET", "/api/v1/exchange-rate", {
      token: access,
      query: { baseCurrency: "USD", quoteCurrency: "KRW" },
    });
    if (fx.status === 200) {
      const result = (fx.payload as { result?: { midRate?: string; rate?: string } })?.result;
      const rate = result?.midRate || result?.rate;
      if (rate) {
        await admin.from("market_prices").upsert(
          { ticker: "USDKRW", price: toNumber(rate), currency: "KRW" },
          { onConflict: "ticker" },
        );
      }
    }

    const summary: Array<{ currency: string; holdings: number; cash: number }> = [];
    for (const acct of brokerage) {
      const seq = Number(acct.accountSeq);
      if (!Number.isFinite(seq)) continue;
      const hold = await tossRequest("GET", "/api/v1/holdings", {
        token: access,
        accountSeq: seq,
      });
      if (hold.status !== 200) {
        const ip = isIpBlocked(hold.status, hold.payload) ? await egressIp() : null;
        return json(
          { ok: false, error: humanize(hold.status, hold.payload, ip), egress_ip: ip },
          isIpBlocked(hold.status, hold.payload) ? 403 : 400,
        );
      }
      const items =
        ((hold.payload as { result?: { items?: Array<Record<string, unknown>> } })?.result?.items) ||
        [];
      const byCcy: Record<"KRW" | "USD", Mapped[]> = { KRW: [], USD: [] };
      for (const item of items) {
        const mapped = mapHolding(item);
        if (!mapped) continue;
        byCcy[mapped.currency].push(mapped);
      }

      const cash: Record<"KRW" | "USD", number> = { KRW: 0, USD: 0 };
      for (const ccy of ["KRW", "USD"] as const) {
        const bp = await tossRequest("GET", "/api/v1/buying-power", {
          token: access,
          accountSeq: seq,
          query: { currency: ccy },
        });
        if (bp.status === 200) {
          cash[ccy] = toNumber(
            (bp.payload as { result?: { cashBuyingPower?: string } })?.result?.cashBuyingPower,
          );
        }
      }

      for (const ccy of ["KRW", "USD"] as const) {
        const rows = byCcy[ccy];
        if (!rows.length && cash[ccy] <= 0) continue;
        let { data: existing } = await admin
          .from("accounts")
          .select("id")
          .eq("user_id", user.id)
          .eq("institution", INSTITUTION)
          .eq("currency", ccy)
          .maybeSingle();
        if (!existing?.id) {
          const ins = await admin
            .from("accounts")
            .insert({
              user_id: user.id,
              institution: INSTITUTION,
              account_type: "brokerage",
              currency: ccy,
              ownership: "joint",
              cash_balance: 0,
            })
            .select("id")
            .single();
          if (ins.error || !ins.data) {
            const lean = await admin
              .from("accounts")
              .insert({
                user_id: user.id,
                institution: INSTITUTION,
                account_type: "brokerage",
                currency: ccy,
              })
              .select("id")
              .single();
            if (lean.error || !lean.data) {
              return json({ ok: false, error: ins.error?.message || "계좌 생성 실패" }, 400);
            }
            existing = lean.data;
          } else {
            existing = ins.data;
          }
        }
        const accountId = existing.id as string;
        const keep = new Set<string>();
        for (const h of rows) {
          keep.add(h.ticker);
          await admin.from("holdings").upsert(
            {
              account_id: accountId,
              ticker: h.ticker,
              name: h.name,
              quantity: h.quantity,
              avg_price: h.avg_price,
              currency: h.currency,
              updated_at: new Date().toISOString(),
            },
            { onConflict: "account_id,ticker" },
          );
          if (h.last_price) {
            await admin.from("market_prices").upsert(
              { ticker: h.ticker, price: h.last_price, currency: h.currency },
              { onConflict: "ticker" },
            );
          }
        }
        const { data: existingH } = await admin
          .from("holdings")
          .select("id,ticker")
          .eq("account_id", accountId);
        for (const row of existingH || []) {
          if (!keep.has(row.ticker)) {
            await admin.from("holdings").delete().eq("id", row.id);
          }
        }
        await admin.from("accounts").update({ cash_balance: cash[ccy] }).eq("id", accountId);
        summary.push({ currency: ccy, holdings: rows.length, cash: cash[ccy] });
      }
    }

    return json({ ok: true, institution: INSTITUTION, accounts: summary });
  } catch (e) {
    if (e instanceof Response) return e;
    return json({ ok: false, error: e instanceof Error ? e.message : "toss-sync failed" }, 500);
  }
});
