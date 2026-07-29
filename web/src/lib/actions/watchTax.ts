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
  if (message.toLowerCase().includes("duplicate")) return "이미 등록된 항목입니다.";
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

function num(v: FormDataEntryValue | null) {
  const n = Number(v);
  return Number.isFinite(n) ? n : NaN;
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
    revalidatePath("/more/tax");
    return ok(`${tax_year}년 세금 기록을 저장했습니다.`);
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}
