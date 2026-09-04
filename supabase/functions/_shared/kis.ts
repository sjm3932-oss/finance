// Korea Investment Open API helpers (inquiry only). Port of scripts/kis_client.py + sync_kis.py.
import type { SupabaseClient } from "jsr:@supabase/supabase-js@2";
import { estimateHoldingDividends, mergeEstimatedDividends, normalizeStoredDividendTickers } from "./yahooDividends.ts";
import { SYNC_REVISION } from "./syncRevision.ts";

export const KIS_REAL_BASE = "https://openapi.koreainvestment.com:9443";
export const KIS_DEMO_BASE = "https://openapivts.koreainvestment.com:29443";
export const INSTITUTION = "한국투자증권";
export const DEFAULT_ACCOUNTS = "64209634-01,64209634-21,64209634-22,64209634-29";
const PRODUCT_LABELS: Record<string, string> = {
  "01": "위탁",
  "21": "ISA",
  "22": "개인연금",
  "29": "퇴직연금",
};

export function productLabel(code: string): string {
  const name = PRODUCT_LABELS[code];
  return name ? `${code} ${name}` : code;
}

export function productMemo(code: string): string {
  return productLabel(code);
}

export function memoProductCode(memo: unknown): string | null {
  const s = String(memo || "").trim();
  if (!s || s.includes("합산") || s.includes("·")) return null;
  if (s.length >= 2 && /^\d{2}/.test(s)) return s.slice(0, 2);
  return null;
}

const ISA_FUND_TICKER = "ISA-FUND";
const ISA_FUND_HOLDING_NAME = "ISA 펀드";
const ISA_OTHER_ASSET_NAME = "한국투자증권 ISA(21) 펀드";

const DIVIDEND_NAME_HINTS = ["배당", "분배"];
const DIVIDEND_RIGHT_CODES = new Set(["03", "04", "17", "18", "74", "75", "3", "4"]);

export type Json = Record<string, unknown>;
export type AccountSpec = [string, string];

type Holding = {
  ticker: string;
  name: string;
  quantity: number;
  avg_price: number;
  currency: string;
  last_price: number;
};

type Fill = {
  external_id: string;
  ticker: string;
  trade_type: string;
  price: number;
  quantity: number;
  fee: number;
  currency: string;
  trade_date: string;
  reason: string;
  product?: string;
};

type Dividend = {
  external_id: string;
  ticker: string;
  name: string;
  pay_date: string;
  amount: number;
  currency: string;
  memo: string;
  product?: string;
};

export function kisBase(env: string): string {
  return ["demo", "paper", "vts"].includes(String(env).toLowerCase())
    ? KIS_DEMO_BASE
    : KIS_REAL_BASE;
}

export function isDemo(env: string): boolean {
  return ["demo", "paper", "vts"].includes(String(env).toLowerCase());
}

export function toNumber(raw: unknown): number {
  if (raw === null || raw === undefined || raw === "") return 0;
  const n = Number(String(raw).replace(/,/g, "").trim());
  return Number.isFinite(n) ? n : 0;
}

export function pick(row: unknown, ...keys: string[]): unknown {
  if (!row || typeof row !== "object") return "";
  const obj = row as Json;
  const lower: Json = {};
  for (const [k, v] of Object.entries(obj)) lower[k.toLowerCase()] = v;
  for (const key of keys) {
    const val = obj[key];
    if (val !== undefined && val !== null && val !== "") return val;
    const v2 = lower[key.toLowerCase()];
    if (v2 !== undefined && v2 !== null && v2 !== "") return v2;
  }
  return "";
}

export function yyyymmdd(raw: unknown): string | null {
  const s = String(raw || "").trim().replace(/-/g, "");
  if (s.length >= 8 && /^\d{8}/.test(s.slice(0, 8))) {
    return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
  }
  const orig = String(raw || "");
  if (orig.length >= 10 && orig[4] === "-" && orig[7] === "-") return orig.slice(0, 10);
  return null;
}

export function normalizeKrTicker(raw: unknown): string {
  let t = String(raw || "").trim().toUpperCase();
  if (t.endsWith(".KS") || t.endsWith(".KQ")) t = t.slice(0, -3);
  // KIS sometimes pads an A-prefix: 00000A458730 → 458730
  const aIdx = t.indexOf("A");
  if (
    aIdx >= 0 &&
    /^\d*$/.test(t.slice(0, aIdx)) &&
    /^\d+$/.test(t.slice(aIdx + 1))
  ) {
    t = t.slice(aIdx + 1);
  }
  if (/^\d+$/.test(t) && t.length <= 6) return t.padStart(6, "0");
  if (/^\d+$/.test(t) && t.length > 6) return t.slice(-6);
  return t;
}

export function normalizeUsTicker(raw: unknown): string {
  let t = String(raw || "").trim().toUpperCase();
  if (t.startsWith("US") && t.length > 6 && !/^\d+$/.test(t.slice(2))) t = t.slice(2);
  return t;
}

export function parseAccountSpec(raw: string): AccountSpec | null {
  const s = String(raw || "").trim().replace(/\s/g, "");
  if (!s) return null;
  if (s.includes("-")) {
    const [left, right] = s.split("-", 2);
    const cano = (left.match(/\d/g) || []).join("");
    const prod = (right.match(/\d/g) || []).join("").slice(0, 2);
    if (cano.length >= 8 && prod) return [cano.slice(0, 8), prod.padStart(2, "0")];
    return null;
  }
  const digits = (s.match(/\d/g) || []).join("");
  if (digits.length >= 10) return [digits.slice(0, 8), digits.slice(8, 10)];
  if (digits.length === 8) return [digits, "01"];
  return null;
}

export function parseAccounts(cano: string, product: string, accountsCsv: string): AccountSpec[] {
  const out: AccountSpec[] = [];
  const seen = new Set<string>();
  const chunks = String(accountsCsv || "").split(",").map((p) => p.trim()).filter(Boolean);
  if (cano.trim()) {
    const spec = parseAccountSpec(
      cano.includes("-") ? cano : `${cano.trim()}-${(product.trim() || "01")}`
    );
    if (spec) chunks.unshift(`${spec[0]}-${spec[1]}`);
  }
  for (const chunk of chunks) {
    const spec = parseAccountSpec(chunk);
    if (spec && !seen.has(`${spec[0]}-${spec[1]}`)) {
      seen.add(`${spec[0]}-${spec[1]}`);
      out.push(spec);
    }
  }
  return out;
}

export function maskKey(key: string): string {
  const s = String(key || "").trim();
  if (!s) return "";
  if (s.length <= 6) return "••••";
  return `${s.slice(0, 4)}…${s.slice(-2)}`;
}

export function settingsPublic(row: {
  app_key?: string | null;
  app_secret?: string | null;
  accounts?: string | null;
  env?: string | null;
}) {
  const appKey = String(row.app_key || "").trim();
  const appSecret = String(row.app_secret || "").trim();
  const accounts = String(row.accounts || "").trim();
  return {
    configured: !!(appKey && appSecret && parseAccounts("", "01", accounts).length),
    app_key_masked: maskKey(appKey),
    accounts,
    env: String(row.env || "real") === "demo" ? "demo" : "real",
  };
}

function outputRows(payload: unknown, ...keys: string[]): Json[] {
  if (!payload || typeof payload !== "object") return [];
  const obj = payload as Json;
  let blob: unknown;
  for (const key of keys) {
    if (key in obj) {
      blob = obj[key];
      break;
    }
    for (const [actual, val] of Object.entries(obj)) {
      if (actual.toLowerCase() === key.toLowerCase()) {
        blob = val;
        break;
      }
    }
    if (blob !== undefined) break;
  }
  if (blob === undefined) return [];
  if (Array.isArray(blob)) return blob.filter((x) => x && typeof x === "object") as Json[];
  if (blob && typeof blob === "object") return [blob as Json];
  return [];
}

export function mapDomesticHolding(item: Json): Holding | null {
  const ticker = normalizeKrTicker(pick(item, "pdno", "shtn_pdno"));
  if (!ticker) return null;
  const qty = toNumber(pick(item, "hldg_qty", "ord_psbl_qty"));
  if (qty <= 0) return null;
  return {
    ticker,
    name: String(pick(item, "prdt_name", "item_name") || ticker).trim() || ticker,
    quantity: qty,
    avg_price: toNumber(pick(item, "pchs_avg_pric", "pchs_avg_unpr")),
    currency: "KRW",
    last_price: toNumber(pick(item, "prpr", "now_pric2")),
  };
}

export function mapOverseasHolding(item: Json): Holding | null {
  const ticker = normalizeUsTicker(pick(item, "ovrs_pdno", "pdno", "item_cd"));
  if (!ticker) return null;
  const qty = toNumber(pick(item, "ovrs_cblc_qty", "hldg_qty", "cblc_qty13"));
  if (qty <= 0) return null;
  let currency = String(pick(item, "tr_crcy_cd", "crcy_cd") || "USD").toUpperCase();
  if (!["USD", "HKD", "JPY", "CNY", "EUR"].includes(currency)) currency = "USD";
  if (currency !== "USD") currency = "USD";
  return {
    ticker,
    name: String(pick(item, "ovrs_item_name", "prdt_name", "item_name") || ticker).trim() || ticker,
    quantity: qty,
    avg_price: toNumber(pick(item, "pchs_avg_pric", "avg_unpr", "pchs_avg_unpr3")),
    currency,
    last_price: toNumber(pick(item, "now_pric2", "ovrs_now_pric1", "prpr")),
  };
}

export function mergeHoldings(rows: Holding[]): Holding[] {
  const byTicker = new Map<string, Holding>();
  for (const row of rows) {
    const key = `${row.ticker}|${row.currency}`;
    const prev = byTicker.get(key);
    if (!prev) {
      byTicker.set(key, { ...row });
      continue;
    }
    const q1 = toNumber(prev.quantity);
    const q2 = toNumber(row.quantity);
    const qty = q1 + q2;
    if (qty > 0) {
      prev.avg_price = (toNumber(prev.avg_price) * q1 + toNumber(row.avg_price) * q2) / qty;
    }
    prev.quantity = qty;
    if (row.last_price) prev.last_price = row.last_price;
    if (row.name && !prev.name) prev.name = row.name;
  }
  return [...byTicker.values()];
}

export function holdingsByCurrency(rows: Holding[]): Record<string, Holding[]> {
  const out: Record<string, Holding[]> = { KRW: [], USD: [] };
  for (const row of mergeHoldings(rows)) {
    const bucket = row.currency in out ? row.currency : "KRW";
    out[bucket].push(row);
  }
  return out;
}

export function domesticCash(summary: Json | null): number {
  if (!summary) return 0;
  return toNumber(pick(summary, "dnca_tot_amt", "nxdy_excc_amt", "prvs_rcdl_excc_amt", "nass_amt"));
}

export function overseasCash(rows: Json[], currency = "USD"): number {
  let total = 0;
  let found = false;
  for (const row of rows) {
    const ccy = String(pick(row, "crcy_cd", "tr_crcy_cd") || "").toUpperCase();
    if (ccy && ccy !== currency) continue;
    const amt = toNumber(
      pick(row, "frcr_dncl_amt_2", "frcr_dncl_amt", "dncl_amt", "frcr_cblc_amt", "cblc_amt", "frcr_evlu_amt2")
    );
    if (amt || ccy === currency) {
      found = true;
      total += amt;
    }
  }
  if (found) return total;
  if (rows.length === 1) {
    return toNumber(pick(rows[0], "frcr_dncl_amt_2", "frcr_dncl_amt", "dncl_amt", "frcr_cblc_amt"));
  }
  return 0;
}

function tradeType(code: unknown, name: unknown): string | null {
  const raw = String(code || "").trim();
  const label = String(name || "");
  if (raw === "02" || raw === "2" || raw === "BUY" || label.includes("매수")) return "buy";
  if (raw === "01" || raw === "1" || raw === "SELL" || label.includes("매도")) return "sell";
  return null;
}

export function mapDomesticFill(item: Json, cano: string): Fill | null {
  const qty = toNumber(pick(item, "tot_ccld_qty", "ccld_qty", "ft_ccld_qty"));
  if (qty <= 0) return null;
  const price = toNumber(pick(item, "avg_prvs", "ccld_avg_unpr", "avg_ccld_unpr", "ccld_unpr"));
  if (price <= 0) return null;
  const tt = tradeType(pick(item, "sll_buy_dvsn_cd", "sll_buy_dvsn"), pick(item, "sll_buy_dvsn_name", "trad_dvsn_name"));
  if (!tt) return null;
  const odno = String(pick(item, "odno", "ord_no") || "").trim();
  if (!odno) return null;
  const ticker = normalizeKrTicker(pick(item, "pdno", "shtn_pdno"));
  if (!ticker) return null;
  const tradeDate = yyyymmdd(pick(item, "ord_dt", "ord_gno_dt", "ccld_dt"));
  if (!tradeDate) return null;
  let fee = toNumber(pick(item, "tot_tr_cost", "cmsn_amt", "tr_tax")) + toNumber(pick(item, "tr_tax", "trde_tax"));
  if (toNumber(pick(item, "tot_tr_cost"))) fee = toNumber(pick(item, "tot_tr_cost"));
  return {
    external_id: `kis:kr:${cano}:${tradeDate}:${odno}`,
    ticker,
    trade_type: tt,
    price,
    quantity: qty,
    fee,
    currency: "KRW",
    trade_date: tradeDate,
    reason: "한투 체결",
  };
}

export function mapOverseasFill(item: Json, cano: string): Fill | null {
  const qty = toNumber(pick(item, "ft_ccld_qty", "ccld_qty", "tot_ccld_qty"));
  if (qty <= 0) return null;
  const price = toNumber(pick(item, "ft_ccld_unpr3", "ft_ccld_unpr", "avg_prvs", "ccld_unpr"));
  if (price <= 0) return null;
  const tt = tradeType(pick(item, "sll_buy_dvsn_cd", "sll_buy_dvsn"), pick(item, "sll_buy_dvsn_name", "trad_dvsn_name"));
  if (!tt) return null;
  const odno = String(pick(item, "odno", "ord_no") || "").trim();
  if (!odno) return null;
  const ticker = normalizeUsTicker(pick(item, "pdno", "ovrs_pdno"));
  if (!ticker) return null;
  const tradeDate = yyyymmdd(pick(item, "ord_dt", "ccld_dt", "trad_dt"));
  if (!tradeDate) return null;
  let currency = String(pick(item, "tr_crcy_cd", "crcy_cd") || "USD").toUpperCase();
  if (currency !== "USD") currency = "USD";
  return {
    external_id: `kis:us:${cano}:${tradeDate}:${odno}`,
    ticker,
    trade_type: tt,
    price,
    quantity: qty,
    fee: toNumber(pick(item, "tr_cmsn", "cmsn_amt", "ovrs_cmsn")),
    currency,
    trade_date: tradeDate,
    reason: "한투 체결",
  };
}

function looksLikeDividend(code: unknown, ...names: unknown[]): boolean {
  const raw = String(code || "").trim();
  const padded = /^\d+$/.test(raw) ? raw.padStart(2, "0") : raw;
  if (DIVIDEND_RIGHT_CODES.has(raw) || DIVIDEND_RIGHT_CODES.has(padded)) return true;
  const blob = names.map((n) => String(n || "")).join(" ");
  return DIVIDEND_NAME_HINTS.some((h) => blob.includes(h));
}

export function mapDomesticDividend(item: Json, cano: string): Dividend | null {
  const nameBits = [
    pick(item, "rght_type_name", "rght_type_cd_name", "trad_dvsn_name"),
    pick(item, "rght_type_cd"),
  ];
  if (!looksLikeDividend(pick(item, "rght_type_cd"), ...nameBits)) return null;
  let amount = toNumber(
    pick(item, "last_alct_amt", "alct_amt", "cash_alct_amt", "csnc_amt", "tot_alct_amt", "dvdn_amt", "rfus_amt", "stck_dvdn_unpr")
  );
  const tax = toNumber(pick(item, "intt_tax", "tax_amt", "stlm_tax"));
  if (amount > 0 && tax > 0 && tax < amount) amount = amount - tax;
  if (amount <= 0) return null;
  const ticker = normalizeKrTicker(pick(item, "pdno", "shtn_pdno"));
  if (!ticker) return null;
  const payDate = yyyymmdd(
    pick(item, "pay_dt", "alct_dt", "cash_alct_dt", "dvdn_pay_dt", "rght_offr_end_dt", "acpl_bass_dt", "bass_dt", "stnd_dt")
  );
  if (!payDate) return null;
  return {
    external_id: `kis:div:kr:${cano}:${payDate}:${ticker}:${amount.toFixed(4)}`,
    ticker,
    name: String(pick(item, "prdt_name") || ticker).trim() || ticker,
    pay_date: payDate,
    amount,
    currency: "KRW",
    memo: String(pick(item, "rght_type_name") || "한투 배당").trim() || "한투 배당",
  };
}

export function mapOverseasDividend(item: Json, cano: string): Dividend | null {
  const nameBits = [
    pick(item, "sll_buy_dvsn_name", "trad_dvsn_name", "tr_type_name", "tr_tp_name", "dvsn_name", "rght_type_name"),
    pick(item, "sll_buy_dvsn_cd", "tr_type_cd", "tr_tp_cd", "rght_type_cd"),
  ];
  if (!looksLikeDividend(pick(item, "sll_buy_dvsn_cd", "tr_type_cd", "tr_tp_cd", "rght_type_cd"), ...nameBits)) return null;
  const amount = Math.abs(
    toNumber(
      pick(
        item,
        "trst_amt",
        "frcr_tr_amt",
        "tr_amt",
        "ccld_amt",
        "ft_ccld_amt3",
        "alct_amt",
        "alct_frcr_unpr",
        "excc_amt",
        "frcr_excc_amt"
      )
    )
  );
  if (amount <= 0) return null;
  const ticker = normalizeUsTicker(pick(item, "pdno", "ovrs_pdno", "ovrs_item_cd"));
  if (!ticker) return null;
  const payDate = yyyymmdd(
    pick(item, "trad_dt", "erlm_dt", "ccld_dt", "stlm_dt", "pay_dt", "bass_dt", "acpl_bass_dt")
  );
  if (!payDate) return null;
  let currency = String(pick(item, "tr_crcy_cd", "crcy_cd") || "USD").toUpperCase();
  if (currency !== "USD") currency = "USD";
  return {
    external_id: `kis:div:us:${cano}:${payDate}:${ticker}:${amount.toFixed(4)}`,
    ticker,
    name: String(pick(item, "prdt_name", "ovrs_item_name") || ticker).trim() || ticker,
    pay_date: payDate,
    amount,
    currency,
    memo: String(pick(item, "sll_buy_dvsn_name", "trad_dvsn_name", "tr_tp_name", "rght_type_name") || "한투 배당").trim() || "한투 배당",
  };
}

function parseYmd(s: string): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

function fmtYmd(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function dateWindows(start: string, end: string, days: number): [string, string][] {
  const step = Math.max(1, days);
  let cur = parseYmd(start);
  const last = parseYmd(end);
  if (cur > last) return [];
  const out: [string, string][] = [];
  while (cur <= last) {
    const nxt = new Date(cur);
    nxt.setUTCDate(nxt.getUTCDate() + step - 1);
    const endWin = nxt > last ? last : nxt;
    out.push([fmtYmd(cur), fmtYmd(endWin)]);
    cur = new Date(endWin);
    cur.setUTCDate(cur.getUTCDate() + 1);
  }
  return out;
}

export function fmtYyyymmdd(d: string): string {
  return d.replace(/-/g, "");
}

export function kstToday(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

export function lookbackRange(days: number): [string, string] {
  const end = parseYmd(kstToday());
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - Math.max(1, days));
  return [fmtYmd(start), fmtYmd(end)];
}

export function humanizeKisError(status: number, payload: unknown): string {
  let code = "";
  let message = "";
  if (payload && typeof payload === "object") {
    const p = payload as Json;
    code = String(p.msg_cd || p.error_code || "");
    message = String(p.msg1 || p.msg || p.error || "");
    const err = p.error;
    if (err && typeof err === "object") {
      const e = err as Json;
      code = code || String(e.code || "");
      message = message || String(e.message || "");
    }
  }
  if (code === "EGW00201" || status === 429) return "한투 API 호출 한도를 넘었습니다. 잠시 후 다시 시도하세요.";
  if (status === 403 || code === "EGW00204") {
    return "한투 Open API가 이 IP를 막았습니다. KIS Developers → 앱키 관리에서 IP 제한을 끄거나, 아래 표시 IP를 허용하세요.";
  }
  if (status === 401 || code === "EGW00121" || code === "EGW00123" || code === "EGW00002") {
    return "한투 인증이 실패했습니다. 앱키와 앱시크릿을 확인하세요.";
  }
  if (code === "EGW00133") return "한투 접근토큰이 이미 발급되어 있습니다. 잠시 후 다시 시도하세요.";
  if (message) return message.includes("한투") ? message : `한투 API: ${message}`;
  if (code) return `한투 API 오류 (${code})`;
  return `한투 API HTTP ${status}`;
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

type KisCtx = {
  env: string;
  base: string;
  appkey: string;
  appsecret: string;
  token: string;
};

async function kisRequest(
  method: string,
  path: string,
  ctx: Pick<KisCtx, "base" | "appkey" | "appsecret"> & { token?: string },
  opts: { trId?: string; trCont?: string; query?: Record<string, string>; jsonBody?: unknown } = {}
): Promise<{ status: number; payload: unknown; headers: Record<string, string> }> {
  let url = ctx.base + path;
  if (opts.query) url += "?" + new URLSearchParams(opts.query).toString();
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json; charset=utf-8",
    appkey: ctx.appkey,
    appsecret: ctx.appsecret,
    custtype: "P",
  };
  if (ctx.token) headers.authorization = `Bearer ${ctx.token}`;
  if (opts.trId) headers.tr_id = opts.trId;
  if (opts.trCont) headers.tr_cont = opts.trCont;
  const res = await fetch(url, {
    method,
    headers,
    body: opts.jsonBody !== undefined ? JSON.stringify(opts.jsonBody) : undefined,
  });
  const text = await res.text();
  let payload: unknown = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = { raw: text.slice(0, 500) };
  }
  const hdrs: Record<string, string> = {};
  res.headers.forEach((v, k) => {
    hdrs[k.toLowerCase()] = v;
  });
  return { status: res.status, payload, headers: hdrs };
}

function tokenStillValid(expiresAt: string | null | undefined): boolean {
  if (!expiresAt) return false;
  const until = Date.parse(expiresAt);
  if (!Number.isFinite(until)) return false;
  return Date.now() + 5 * 60 * 1000 < until;
}

async function loadDbToken(admin: SupabaseClient): Promise<string | null> {
  const { data } = await admin
    .from("kis_api_settings")
    .select("access_token,token_expires_at")
    .eq("id", 1)
    .maybeSingle();
  const token = String(data?.access_token || "").trim();
  if (!token) return null;
  if (!tokenStillValid(data?.token_expires_at)) return null;
  return token;
}

async function saveDbToken(admin: SupabaseClient, token: string, expiresIn: number): Promise<void> {
  const until = new Date(Date.now() + Math.max(60, expiresIn - 60) * 1000).toISOString();
  await admin.from("kis_api_settings").update({ access_token: token, token_expires_at: until }).eq("id", 1);
}

export async function issueToken(
  admin: SupabaseClient,
  appkey: string,
  appsecret: string,
  base: string
): Promise<string> {
  const cached = await loadDbToken(admin);
  if (cached) return cached;
  const body = { grant_type: "client_credentials", appkey, appsecret };
  let { status, payload } = await kisRequest("POST", "/oauth2/tokenP", { base, appkey, appsecret }, { jsonBody: body });
  let token = payload && typeof payload === "object" ? String((payload as Json).access_token || "") : "";
  let expiresIn = payload && typeof payload === "object" ? toNumber((payload as Json).expires_in) || 86400 : 86400;
  if (status === 200 && token) {
    await saveDbToken(admin, token, expiresIn);
    return token;
  }
  await sleep(1200);
  const again = await loadDbToken(admin);
  if (again) return again;
  ({ status, payload } = await kisRequest("POST", "/oauth2/tokenP", { base, appkey, appsecret }, { jsonBody: body }));
  token = payload && typeof payload === "object" ? String((payload as Json).access_token || "") : "";
  expiresIn = payload && typeof payload === "object" ? toNumber((payload as Json).expires_in) || 86400 : 86400;
  if (status === 200 && token) {
    await saveDbToken(admin, token, expiresIn);
    return token;
  }
  throw new Error(humanizeKisError(status, payload));
}

async function pagedGet(
  ctx: KisCtx,
  opts: {
    path: string;
    trId: string;
    query: Record<string, string>;
    fkKey: string;
    nkKey: string;
    outputKey?: string;
    extraOutput?: string;
    maxPages?: number;
  }
): Promise<{ rows: Json[]; summary: Json | null }> {
  const rows: Json[] = [];
  let summary: Json | null = null;
  let trCont = "";
  const q = { ...opts.query };
  const maxPages = opts.maxPages ?? 40;
  for (let i = 0; i < maxPages; i++) {
    if (i) await sleep(150);
    let { status, payload, headers } = await kisRequest("GET", opts.path, ctx, {
      trId: opts.trId,
      trCont,
      query: q,
    });
    let retries = 0;
    while (
      retries < 4 &&
      (status === 429 ||
        (payload && typeof payload === "object" && String((payload as Json).msg_cd || "") === "EGW00201"))
    ) {
      await sleep(1200 + retries * 400);
      retries += 1;
      ({ status, payload, headers } = await kisRequest("GET", opts.path, ctx, {
        trId: opts.trId,
        trCont,
        query: q,
      }));
    }
    const rt = payload && typeof payload === "object" ? String((payload as Json).rt_cd || "0") : "0";
    if (status !== 200 || (rt !== "0" && rt !== "0.0")) {
      throw new Error(humanizeKisError(status, payload));
    }
    rows.push(...outputRows(payload, opts.outputKey || "output1", "output"));
    const extra = outputRows(payload, opts.extraOutput || "output2");
    if (extra.length) summary = extra[0];
    const trContHdr = (headers["tr_cont"] || "").trim();
    if (payload && typeof payload === "object") {
      const p = payload as Json;
      q[opts.fkKey] = String(p[opts.fkKey.toLowerCase()] || p[opts.fkKey] || "");
      q[opts.nkKey] = String(p[opts.nkKey.toLowerCase()] || p[opts.nkKey] || "");
    }
    if (trContHdr !== "M" && trContHdr !== "F") break;
    trCont = "N";
  }
  return { rows, summary };
}

async function fetchDomesticBalance(ctx: KisCtx, cano: string, prod: string): Promise<{ holdings: Holding[]; cash: number }> {
  const query = {
    CANO: cano,
    ACNT_PRDT_CD: prod,
    AFHR_FLPR_YN: "N",
    OFL_YN: "",
    INQR_DVSN: "02",
    UNPR_DVSN: "01",
    FUND_STTL_ICLD_YN: "N",
    FNCG_AMT_AUTO_RDPT_YN: "N",
    PRCS_DVSN: "00",
    CTX_AREA_FK100: "",
    CTX_AREA_NK100: "",
  };
  try {
    const { rows, summary } = await pagedGet(ctx, {
      path: "/uapi/domestic-stock/v1/trading/inquire-balance",
      trId: isDemo(ctx.env) ? "VTTC8434R" : "TTTC8434R",
      query,
      fkKey: "CTX_AREA_FK100",
      nkKey: "CTX_AREA_NK100",
      outputKey: "output1",
      extraOutput: "output2",
    });
    return {
      holdings: rows.map(mapDomesticHolding).filter((x): x is Holding => !!x),
      cash: domesticCash(summary),
    };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    if (!msg.includes("위탁계좌인 경우만") && !msg.includes("APAC0489")) throw e;
  }
  try {
    const { rows, summary } = await pagedGet(ctx, {
      path: "/uapi/domestic-stock/v1/trading/pension/inquire-balance",
      trId: "TTTC2208R",
      query: {
        CANO: cano,
        ACNT_PRDT_CD: prod,
        ACCA_DVSN_CD: "00",
        INQR_DVSN: "00",
        CTX_AREA_FK100: "",
        CTX_AREA_NK100: "",
      },
      fkKey: "CTX_AREA_FK100",
      nkKey: "CTX_AREA_NK100",
      outputKey: "output1",
      extraOutput: "output2",
    });
    return {
      holdings: rows.map(mapDomesticHolding).filter((x): x is Holding => !!x),
      cash: domesticCash(summary),
    };
  } catch (e) {
    console.log("pension balance skip", cano, prod, e);
    return { holdings: [], cash: 0 };
  }
}

async function fetchAccountOverview(
  ctx: KisCtx,
  cano: string,
  prod: string
): Promise<{ nass: number; cash: number; ok: boolean }> {
  try {
    const { rows, summary } = await pagedGet(ctx, {
      path: "/uapi/domestic-stock/v1/trading/inquire-account-balance",
      trId: "CTRP6548R",
      query: { CANO: cano, ACNT_PRDT_CD: prod },
      fkKey: "CTX_AREA_FK100",
      nkKey: "CTX_AREA_NK100",
      outputKey: "output1",
      extraOutput: "output2",
      maxPages: 1,
    });
    let nass = toNumber(summary?.nass_tot_amt || summary?.evlu_amt_smtl);
    const cash = toNumber(summary?.cma_evlu_amt) || toNumber(summary?.tot_dncl_amt);
    if (nass <= 0) {
      for (const row of rows) {
        nass = Math.max(nass, toNumber(row.evlu_amt || row.real_nass_amt));
      }
    }
    return { nass, cash, ok: true };
  } catch {
    return { nass: 0, cash: 0, ok: false };
  }
}

async function deleteIsaOtherAsset(admin: SupabaseClient, userId: string): Promise<void> {
  const { data: existing } = await admin
    .from("other_assets")
    .select("id")
    .eq("user_id", userId)
    .eq("name", ISA_OTHER_ASSET_NAME)
    .limit(1);
  if (existing?.[0]?.id) await admin.from("other_assets").delete().eq("id", existing[0].id);
}

async function fetchOverseasBalance(ctx: KisCtx, cano: string, prod: string): Promise<Holding[]> {
  const { rows } = await pagedGet(ctx, {
    path: "/uapi/overseas-stock/v1/trading/inquire-balance",
    trId: isDemo(ctx.env) ? "VTTS3012R" : "TTTS3012R",
    query: {
      CANO: cano,
      ACNT_PRDT_CD: prod,
      OVRS_EXCG_CD: "NASD",
      TR_CRCY_CD: "USD",
      CTX_AREA_FK200: "",
      CTX_AREA_NK200: "",
    },
    fkKey: "CTX_AREA_FK200",
    nkKey: "CTX_AREA_NK200",
    outputKey: "output1",
    extraOutput: "output2",
  });
  return rows.map(mapOverseasHolding).filter((x): x is Holding => !!x);
}

async function fetchOverseasCash(ctx: KisCtx, cano: string, prod: string): Promise<number> {
  try {
    const { rows } = await pagedGet(ctx, {
      path: "/uapi/overseas-stock/v1/trading/inquire-present-balance",
      trId: isDemo(ctx.env) ? "VTRP6504R" : "CTRP6504R",
      query: {
        CANO: cano,
        ACNT_PRDT_CD: prod,
        WCRC_FRCR_DVSN_CD: "02",
        NATN_CD: "000",
        TR_MKET_CD: "00",
        INQR_DVSN_CD: "00",
      },
      fkKey: "CTX_AREA_FK200",
      nkKey: "CTX_AREA_NK200",
      outputKey: "output2",
      extraOutput: "output3",
      maxPages: 1,
    });
    return overseasCash(rows, "USD");
  } catch {
    return 0;
  }
}

async function fetchDomesticFills(ctx: KisCtx, cano: string, prod: string, start: string, end: string): Promise<Fill[]> {
  const mapped: Fill[] = [];
  const endD = parseYmd(end);
  const innerCut = new Date(endD);
  innerCut.setUTCDate(innerCut.getUTCDate() - 89);
  const innerStart = parseYmd(start) > innerCut ? parseYmd(start) : innerCut;
  const beforeEnd = new Date(innerCut);
  beforeEnd.setUTCDate(beforeEnd.getUTCDate() - 1);
  const windowsInner = dateWindows(fmtYmd(innerStart), end, 30);
  const windowsBefore = parseYmd(start) < innerCut
    ? dateWindows(start, fmtYmd(beforeEnd), 30)
    : [];
  const demo = isDemo(ctx.env);
  const plans: [string, [string, string][]][] = [];
  if (windowsInner.length) plans.push([demo ? "VTTC0081R" : "TTTC0081R", windowsInner]);
  if (windowsBefore.length) plans.push([demo ? "VTSC9215R" : "CTSC9215R", windowsBefore]);
  for (const [trId, windows] of plans) {
    for (const [a, b] of windows) {
      await sleep(150);
      const { rows } = await pagedGet(ctx, {
        path: "/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
        trId,
        query: {
          CANO: cano,
          ACNT_PRDT_CD: prod,
          INQR_STRT_DT: fmtYyyymmdd(a),
          INQR_END_DT: fmtYyyymmdd(b),
          SLL_BUY_DVSN_CD: "00",
          PDNO: "",
          CCLD_DVSN: "01",
          INQR_DVSN: "01",
          INQR_DVSN_3: "00",
          ORD_GNO_BRNO: "",
          ODNO: "",
          INQR_DVSN_1: "",
          CTX_AREA_FK100: "",
          CTX_AREA_NK100: "",
          EXCG_ID_DVSN_CD: "ALL",
        },
        fkKey: "CTX_AREA_FK100",
        nkKey: "CTX_AREA_NK100",
      });
      for (const r of rows) {
        const m = mapDomesticFill(r, cano);
        if (m) mapped.push(m);
      }
    }
  }
  return mapped;
}

async function fetchOverseasFills(ctx: KisCtx, cano: string, prod: string, start: string, end: string): Promise<Fill[]> {
  const mapped: Fill[] = [];
  const trId = isDemo(ctx.env) ? "VTTS3035R" : "TTTS3035R";
  for (const [a, b] of dateWindows(start, end, 30)) {
    await sleep(150);
    const { rows } = await pagedGet(ctx, {
      path: "/uapi/overseas-stock/v1/trading/inquire-ccnl",
      trId,
      query: {
        CANO: cano,
        ACNT_PRDT_CD: prod,
        PDNO: "%",
        ORD_STRT_DT: fmtYyyymmdd(a),
        ORD_END_DT: fmtYyyymmdd(b),
        SLL_BUY_DVSN: "00",
        CCLD_NCCS_DVSN: "01",
        OVRS_EXCG_CD: "%",
        SORT_SQN: "DS",
        ORD_DT: "",
        ORD_GNO_BRNO: "",
        ODNO: "",
        CTX_AREA_NK200: "",
        CTX_AREA_FK200: "",
      },
      fkKey: "CTX_AREA_FK200",
      nkKey: "CTX_AREA_NK200",
      outputKey: "output",
    });
    for (const r of rows) {
      const m = mapOverseasFill(r, cano);
      if (m) mapped.push(m);
    }
  }
  return mapped;
}

async function fetchDomesticDividends(ctx: KisCtx, cano: string, prod: string, start: string, end: string): Promise<Dividend[]> {
  const mapped: Dividend[] = [];
  const seen = new Set<string>();
  for (const [a, b] of dateWindows(start, end, 90)) {
    for (const rght of ["", "03"]) {
      await sleep(150);
      try {
        const { rows } = await pagedGet(ctx, {
          path: "/uapi/domestic-stock/v1/trading/period-rights",
          trId: "CTRGA011R",
          query: {
            INQR_DVSN: "03",
            CANO: cano,
            ACNT_PRDT_CD: prod,
            INQR_STRT_DT: fmtYyyymmdd(a),
            INQR_END_DT: fmtYyyymmdd(b),
            CUST_RNCNO25: "",
            HMID: "",
            RGHT_TYPE_CD: rght,
            PDNO: "",
            PRDT_TYPE_CD: "",
            CTX_AREA_NK100: "",
            CTX_AREA_FK100: "",
          },
          fkKey: "CTX_AREA_FK100",
          nkKey: "CTX_AREA_NK100",
          outputKey: "output",
        });
        let added = 0;
        for (const r of rows) {
          const m = mapDomesticDividend(r, cano);
          if (!m || seen.has(m.external_id)) continue;
          seen.add(m.external_id);
          mapped.push(m);
          added += 1;
        }
        if (added && !rght) break;
      } catch {
        continue;
      }
    }
  }
  return mapped;
}

async function ensureAccount(admin: SupabaseClient, userId: string, currency: string, prod: string): Promise<string> {
  const { data: rows } = await admin
    .from("accounts")
    .select("id,memo")
    .eq("user_id", userId)
    .eq("institution", INSTITUTION)
    .eq("currency", currency);
  for (const row of rows || []) {
    if (memoProductCode(row.memo) === prod) return row.id as string;
  }
  const leftover = (rows || []).find((row) => memoProductCode(row.memo) == null);
  if (leftover?.id) {
    await setProductAccountMemo(admin, leftover.id as string, prod);
    return leftover.id as string;
  }
  const { data, error } = await admin
    .from("accounts")
    .insert({
      user_id: userId,
      institution: INSTITUTION,
      account_type: "brokerage",
      currency,
      ownership: "mine",
      cash_balance: 0,
      memo: productMemo(prod),
    })
    .select("id")
    .single();
  if (error || !data?.id) {
    const fallback = await admin
      .from("accounts")
      .insert({
        user_id: userId,
        institution: INSTITUTION,
        account_type: "brokerage",
        currency,
        memo: productMemo(prod),
      })
      .select("id")
      .single();
    if (fallback.error || !fallback.data?.id) {
      throw new Error(`failed to create ${INSTITUTION} ${prod} ${currency} account`);
    }
    return fallback.data.id as string;
  }
  return data.id as string;
}

async function setProductAccountMemo(admin: SupabaseClient, accountId: string, prod: string): Promise<void> {
  await admin.from("accounts").update({ memo: productMemo(prod) }).eq("id", accountId);
}

async function upsertHoldings(admin: SupabaseClient, accountId: string, rows: Holding[]): Promise<void> {
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
      { onConflict: "account_id,ticker" }
    );
    if (h.last_price) {
      await admin.from("market_prices").upsert(
        { ticker: h.ticker, price: h.last_price, currency: h.currency },
        { onConflict: "ticker" }
      );
    }
  }
  const { data: existing } = await admin.from("holdings").select("id,ticker").eq("account_id", accountId);
  for (const row of existing || []) {
    if (!keep.has(String(row.ticker))) {
      await admin.from("holdings").delete().eq("id", row.id);
    }
  }
}

async function existingTradeKeys(admin: SupabaseClient, accountIds: string[]): Promise<Set<string>> {
  const keys = new Set<string>();
  if (!accountIds.length) return keys;
  const { data } = await admin.from("trades").select("external_id,reason").in("account_id", accountIds);
  for (const row of data || []) {
    const ext = String(row.external_id || "").trim();
    if (ext) keys.add(ext);
    const reason = String(row.reason || "");
    if (reason.startsWith("kis:")) keys.add(reason);
  }
  return keys;
}

async function existingDividendKeys(admin: SupabaseClient, accountIds: string[]): Promise<Set<string>> {
  const keys = new Set<string>();
  if (!accountIds.length) return keys;
  const { data } = await admin.from("dividends").select("external_id").in("account_id", accountIds);
  for (const row of data || []) {
    const ext = String(row.external_id || "").trim();
    if (ext) keys.add(ext);
  }
  return keys;
}

async function insertTrades(
  admin: SupabaseClient,
  userId: string,
  accountIds: Record<string, string>,
  rows: Fill[]
): Promise<Record<string, number>> {
  const known = await existingTradeKeys(admin, Object.values(accountIds));
  const per: Record<string, number> = {};
  for (const row of rows) {
    if (known.has(row.external_id)) continue;
    const accountId =
      (row.product && accountIds[`${row.product}:${row.currency}`]) || accountIds[row.currency];
    if (!accountId) continue;
    const payload: Json = {
      account_id: accountId,
      trade_date: row.trade_date,
      ticker: row.ticker,
      trade_type: row.trade_type,
      price: row.price,
      quantity: row.quantity,
      fee: row.fee,
      currency: row.currency,
      reason: row.reason,
      created_by: userId,
      adjust_holdings: false,
      external_id: row.external_id,
    };
    const { data, error } = await admin.from("trades").insert(payload).select("id");
    if (error || !data?.length) continue;
    known.add(row.external_id);
    per[row.currency] = (per[row.currency] || 0) + 1;
  }
  return per;
}

async function insertDividends(
  admin: SupabaseClient,
  userId: string,
  accountIds: Record<string, string>,
  rows: Dividend[]
): Promise<Record<string, number>> {
  const known = await existingDividendKeys(admin, Object.values(accountIds));
  const per: Record<string, number> = {};
  for (const row of rows) {
    if (known.has(row.external_id)) continue;
    const accountId =
      (row.product && accountIds[`${row.product}:${row.currency}`]) || accountIds[row.currency];
    if (!accountId) continue;
    const { data, error } = await admin.from("dividends").insert({
      user_id: userId,
      account_id: accountId,
      ticker: normalizeKrTicker(row.ticker) || row.ticker,
      name: row.name,
      pay_date: row.pay_date,
      amount: row.amount,
      currency: row.currency,
      memo: row.memo || "한투 배당",
      external_id: row.external_id,
    }).select("id");
    if (error || !data?.length) continue;
    known.add(row.external_id);
    per[row.currency] = (per[row.currency] || 0) + 1;
  }
  return per;
}

export async function loadKisSettings(admin: SupabaseClient): Promise<{
  app_key: string;
  app_secret: string;
  accounts: AccountSpec[];
  env: string;
  accounts_csv: string;
} | null> {
  const { data } = await admin
    .from("kis_api_settings")
    .select("app_key,app_secret,accounts,env")
    .eq("id", 1)
    .maybeSingle();
  if (!data) return null;
  const app_key = String(data.app_key || "").trim();
  const app_secret = String(data.app_secret || "").trim();
  const accounts_csv = String(data.accounts || "").trim();
  const env = String(data.env || "real").trim() || "real";
  const accounts = parseAccounts("", "01", accounts_csv);
  if (!app_key || !app_secret || !accounts.length) return null;
  return { app_key, app_secret, accounts, env, accounts_csv };
}

export async function runKisSync(
  admin: SupabaseClient,
  opts: { userId: string; lookbackDays?: number }
): Promise<{
  ok: true;
  institution: string;
  accounts: Array<Record<string, unknown>>;
  products: Array<Record<string, unknown>>;
  trades: number;
  dividends: number;
  sync_revision: string;
}> {
  const settings = await loadKisSettings(admin);
  if (!settings) {
    throw new Error("한투 앱키를 앱에 저장하세요. 기록하기 → 한투 동기화.");
  }
  const base = kisBase(settings.env);
  const token = await issueToken(admin, settings.app_key, settings.app_secret, base);
  const ctx: KisCtx = {
    env: settings.env,
    base,
    appkey: settings.app_key,
    appsecret: settings.app_secret,
    token,
  };
  const [start, end] = lookbackRange(opts.lookbackDays ?? 365);
  try {
    await normalizeStoredDividendTickers(admin);
  } catch (e) {
    console.log("normalize stored dividend tickers skip", e);
  }

  const fills: Fill[] = [];
  const dividends: Dividend[] = [];
  let isaSeen = false;
  const products: Array<Record<string, unknown>> = [];
  const accountIds: Record<string, string> = {};

  function tagFills(rows: Fill[], prod: string): Fill[] {
    return rows.map((r) => ({ ...r, product: prod }));
  }
  function tagDivs(rows: Dividend[], prod: string): Dividend[] {
    return rows.map((r) => ({ ...r, product: prod }));
  }

  for (let i = 0; i < settings.accounts.length; i++) {
    const [cano, prod] = settings.accounts[i];
    if (i) await sleep(900);
    let krHold: Holding[] = [];
    let krCash = 0;
    let ovCash = 0;
    let usdCash = 0;
    let usHold: Holding[] = [];
    let fund = 0;
    let note = "";
    try {
      const kr = await fetchDomesticBalance(ctx, cano, prod);
      krHold = kr.holdings;
      krCash = kr.cash;
    } catch (e) {
      note = e instanceof Error ? e.message : String(e);
      console.log("domestic balance skip", cano, prod, e);
    }
    if (prod === "21") {
      try {
        const ov = await fetchAccountOverview(ctx, cano, prod);
        if (ov.ok) {
          isaSeen = true;
          ovCash = ov.cash;
          if (!krHold.length && ov.nass > 0) {
            fund = ov.nass;
            krHold.push({
              ticker: ISA_FUND_TICKER,
              name: ISA_FUND_HOLDING_NAME,
              quantity: 1,
              avg_price: fund,
              currency: "KRW",
              last_price: fund,
            });
            if (!note) note = "펀드는 종목 API가 없어 이 계좌 보유로 반영";
          }
        }
      } catch (e) {
        console.log("21 overview skip", e);
        note = note || (e instanceof Error ? e.message : String(e));
      }
    }
    try {
      usHold = await fetchOverseasBalance(ctx, cano, prod);
    } catch (e) {
      console.log("overseas balance skip", cano, prod, e);
    }
    try {
      usdCash = await fetchOverseasCash(ctx, cano, prod);
    } catch (e) {
      console.log("usd cash skip", cano, prod, e);
    }
    const prodFills: Fill[] = [];
    const prodDivs: Dividend[] = [];
    try {
      prodFills.push(...tagFills(await fetchDomesticFills(ctx, cano, prod, start, end), prod));
    } catch (e) {
      console.log("domestic fills skip", cano, prod, e);
    }
    try {
      prodFills.push(...tagFills(await fetchOverseasFills(ctx, cano, prod, start, end), prod));
    } catch (e) {
      console.log("overseas fills skip", cano, prod, e);
    }
    try {
      prodDivs.push(...tagDivs(await fetchDomesticDividends(ctx, cano, prod, start, end), prod));
    } catch (e) {
      console.log("domestic dividends skip", cano, prod, e);
    }
    try {
      const estimated = await estimateHoldingDividends(krHold, {
        fromDate: start,
        toDate: end,
        source: "kis",
      });
      const merged = mergeEstimatedDividends(prodDivs, tagDivs(estimated, prod));
      prodDivs.length = 0;
      prodDivs.push(...merged);
    } catch (e) {
      console.log("yahoo dividend estimate skip", cano, prod, e);
    }
    fills.push(...prodFills);
    dividends.push(...prodDivs);

    const prodHoldings = [...krHold, ...usHold];
    const byCcy = holdingsByCurrency(prodHoldings);
    const cashBy = { KRW: krCash + ovCash, USD: usdCash };
    const tradeCcy = new Set(prodFills.map((m) => m.currency));
    const divCcy = new Set(prodDivs.map((m) => m.currency));
    for (const ccy of ["KRW", "USD"] as const) {
      const rows = byCcy[ccy] || [];
      if (!rows.length && cashBy[ccy] <= 0 && !tradeCcy.has(ccy) && !divCcy.has(ccy)) continue;
      const aid = await ensureAccount(admin, opts.userId, ccy, prod);
      accountIds[`${prod}:${ccy}`] = aid;
      await upsertHoldings(admin, aid, rows);
      await admin.from("accounts").update({ cash_balance: cashBy[ccy] }).eq("id", aid);
      await setProductAccountMemo(admin, aid, prod);
    }

    products.push({
      code: prod,
      label: productLabel(prod),
      holdings: krHold.length + usHold.length,
      cash: krCash + ovCash,
      fund,
      note,
    });
  }

  let tradeCounts: Record<string, number> = {};
  let divCounts: Record<string, number> = {};
  if (Object.keys(accountIds).length) {
    tradeCounts = await insertTrades(admin, opts.userId, accountIds, fills);
    divCounts = await insertDividends(admin, opts.userId, accountIds, dividends);
  }
  try {
    if (isaSeen) await deleteIsaOtherAsset(admin, opts.userId);
  } catch (e) {
    console.log("isa other asset skip", e);
  }

  const summary = products.map((p) => ({
    currency: "KRW",
    product: p.code,
    label: p.label,
    holdings: p.holdings,
    cash: p.cash,
  }));

  const tradeN = Object.values(tradeCounts).reduce((s, n) => s + n, 0);
  const divN = Object.values(divCounts).reduce((s, n) => s + n, 0);
  return {
    ok: true,
    institution: INSTITUTION,
    accounts: summary,
    products,
    trades: tradeN,
    dividends: divN,
    sync_revision: SYNC_REVISION,
  };
}
