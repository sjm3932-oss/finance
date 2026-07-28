"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import type { ActionResult } from "@/lib/record";

function fail(message: string): ActionResult {
  return { ok: false, message };
}
function ok(message: string): ActionResult {
  return { ok: true, message };
}
function humanize(message: string): string {
  if (/[가-힣]/.test(message)) return message;
  if (message.toLowerCase().includes("duplicate")) return "이미 등록된 티커입니다.";
  return "저장에 실패했습니다. 입력값을 확인하세요.";
}

async function requireUser() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) throw new Error("로그인이 필요합니다.");
  return { supabase, user };
}

function str(v: FormDataEntryValue | null) {
  return String(v ?? "").trim();
}
function num(v: FormDataEntryValue | null) {
  const n = Number(v);
  return Number.isFinite(n) ? n : NaN;
}

function normalizeTicker(raw: string) {
  const t = raw.trim().toUpperCase();
  if (/^\d{6}$/.test(t)) return t;
  return t.replace(/\./g, "-");
}

function revalidateWatch() {
  revalidatePath("/more/watchlist");
  revalidatePath("/");
}

function revalidateTax() {
  revalidatePath("/more/tax");
}

export async function upsertWatchlistItem(
  formData: FormData
): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireUser();
    const ticker = normalizeTicker(str(formData.get("ticker")));
    const name = str(formData.get("name")) || ticker;
    const targetRaw = str(formData.get("target_price"));
    const stopRaw = str(formData.get("stop_price"));
    const note = str(formData.get("note")) || null;
    if (!ticker) return fail("티커를 입력하세요.");

    const target = targetRaw === "" ? null : num(formData.get("target_price"));
    const stop = stopRaw === "" ? null : num(formData.get("stop_price"));
    if (target != null && (!Number.isFinite(target) || target < 0)) {
      return fail("목표가를 확인하세요.");
    }
    if (stop != null && (!Number.isFinite(stop) || stop < 0)) {
      return fail("손절가를 확인하세요.");
    }

    const { error } = await supabase.from("watchlist").upsert(
      {
        user_id: user.id,
        ticker,
        name,
        target_price: target && target > 0 ? target : null,
        stop_price: stop && stop > 0 ? stop : null,
        note,
      },
      { onConflict: "user_id,ticker" }
    );
    if (error) return fail(humanize(error.message));
    revalidateWatch();
    return ok(`${ticker} 관심종목에 저장했습니다.`);
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function deleteWatchlistItem(
  formData: FormData
): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireUser();
    const id = str(formData.get("id"));
    if (!id) return fail("항목을 선택하세요.");
    const { error } = await supabase
      .from("watchlist")
      .delete()
      .eq("id", id)
      .eq("user_id", user.id);
    if (error) return fail(humanize(error.message));
    revalidateWatch();
    return ok("삭제했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function acknowledgeWatchAlerts(): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireUser();
    const { error } = await supabase
      .from("price_alert_events")
      .update({ acknowledged: true })
      .eq("user_id", user.id)
      .eq("acknowledged", false);
    if (error) return fail(humanize(error.message));
    revalidateWatch();
    return ok("알림을 모두 확인 처리했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function evaluateWatchAlerts(): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireUser();
    const { data: items } = await supabase
      .from("watchlist")
      .select("id,ticker,target_price,stop_price")
      .eq("user_id", user.id);
    if (!items?.length) return ok("관심종목이 없습니다.");

    const { data: prices } = await supabase
      .from("market_prices")
      .select("ticker,price");
    const pmap = new Map((prices || []).map((p) => [p.ticker, Number(p.price)]));

    let created = 0;
    for (const w of items) {
      const price = pmap.get(w.ticker);
      if (price == null || !Number.isFinite(price)) continue;
      const kinds: Array<{ kind: string; trigger: number }> = [];
      if (w.target_price != null && price >= Number(w.target_price)) {
        kinds.push({ kind: "target", trigger: Number(w.target_price) });
      }
      if (w.stop_price != null && price <= Number(w.stop_price)) {
        kinds.push({ kind: "stop", trigger: Number(w.stop_price) });
      }
      for (const k of kinds) {
        const { data: existing } = await supabase
          .from("price_alert_events")
          .select("id")
          .eq("user_id", user.id)
          .eq("ticker", w.ticker)
          .eq("alert_kind", k.kind)
          .eq("acknowledged", false)
          .limit(1);
        if (existing?.length) continue;
        const { error } = await supabase.from("price_alert_events").insert({
          user_id: user.id,
          watchlist_id: w.id,
          ticker: w.ticker,
          alert_kind: k.kind,
          trigger_price: k.trigger,
          market_price: price,
          acknowledged: false,
        });
        if (!error) created += 1;
      }
    }
    revalidateWatch();
    return ok(
      created > 0 ? `새 알림 ${created}건` : "조건에 해당하는 새 알림 없음"
    );
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function upsertTaxRecord(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireUser();
    const tax_year = Math.trunc(num(formData.get("tax_year")));
    const cum_capital_gain = num(formData.get("cum_capital_gain"));
    const tax_threshold = num(formData.get("tax_threshold"));
    const dividend_tax = num(formData.get("dividend_tax"));

    if (!Number.isFinite(tax_year) || tax_year < 2020 || tax_year > 2100) {
      return fail("세무연도를 확인하세요.");
    }
    if (!Number.isFinite(cum_capital_gain) || cum_capital_gain < 0) {
      return fail("누적 양도차익을 확인하세요.");
    }
    if (!Number.isFinite(tax_threshold) || tax_threshold < 0) {
      return fail("기본공제를 확인하세요.");
    }
    if (!Number.isFinite(dividend_tax) || dividend_tax < 0) {
      return fail("배당세를 확인하세요.");
    }

    const { error } = await supabase.from("tax_records").upsert(
      {
        user_id: user.id,
        tax_year,
        cum_capital_gain,
        tax_threshold,
        dividend_tax,
      },
      { onConflict: "user_id,tax_year" }
    );
    if (error) return fail(humanize(error.message));
    revalidateTax();
    return ok(`${tax_year}년 세금 기록을 저장했습니다.`);
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}
