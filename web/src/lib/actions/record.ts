"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { splitMonthlyPayment, type ActionResult } from "@/lib/record";

function fail(message: string): ActionResult {
  return { ok: false, message };
}

function ok(message: string): ActionResult {
  return { ok: true, message };
}

async function requireUser() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) throw new Error("로그인이 필요합니다.");
  return { supabase, user };
}

function str(v: FormDataEntryValue | null): string {
  return String(v ?? "").trim();
}

function num(v: FormDataEntryValue | null): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : NaN;
}

function revalidateRecord() {
  revalidatePath("/");
  revalidatePath("/holdings");
  revalidatePath("/record");
  revalidatePath("/more/net-worth");
  revalidatePath("/more/other-assets");
}

export async function createAccount(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireUser();
    const institution = str(formData.get("institution"));
    const account_type = str(formData.get("account_type")) || "brokerage";
    const currency = str(formData.get("currency")) || "KRW";
    if (!institution) return fail("금융기관 이름을 입력하세요.");

    const { error } = await supabase.from("accounts").insert({
      user_id: user.id,
      institution,
      account_type,
      currency,
    });
    if (error) return fail(error.message);
    revalidateRecord();
    return ok("계좌를 만들었습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function updateAccountCash(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase } = await requireUser();
    const id = str(formData.get("account_id"));
    const cash_balance = num(formData.get("cash_balance"));
    const ownership = str(formData.get("ownership")) || "joint";
    if (!id) return fail("계좌를 선택하세요.");
    if (!Number.isFinite(cash_balance) || cash_balance < 0) {
      return fail("현금 잔고를 확인하세요.");
    }

    const { error } = await supabase
      .from("accounts")
      .update({ cash_balance, ownership })
      .eq("id", id);
    if (error) return fail(error.message);
    revalidateRecord();
    return ok("계좌 현금·소유를 저장했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function createOtherAsset(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireUser();
    const name = str(formData.get("name"));
    const asset_kind = str(formData.get("asset_kind")) || "other";
    const value_krw = num(formData.get("value_krw"));
    const ownership = str(formData.get("ownership")) || "joint";
    const memo = str(formData.get("memo")) || null;
    if (!name) return fail("이름을 입력하세요.");
    if (!Number.isFinite(value_krw) || value_krw < 0) {
      return fail("평가액을 확인하세요.");
    }

    const { error } = await supabase.from("other_assets").insert({
      user_id: user.id,
      name,
      asset_kind,
      value_krw,
      ownership,
      memo,
      updated_at: new Date().toISOString(),
    });
    if (error) return fail(error.message);
    revalidateRecord();
    return ok("기타자산을 추가했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function updateOtherAssetValue(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase } = await requireUser();
    const id = str(formData.get("id"));
    const value_krw = num(formData.get("value_krw"));
    if (!id) return fail("항목을 선택하세요.");
    if (!Number.isFinite(value_krw) || value_krw < 0) {
      return fail("평가액을 확인하세요.");
    }

    const { error } = await supabase
      .from("other_assets")
      .update({ value_krw, updated_at: new Date().toISOString() })
      .eq("id", id);
    if (error) return fail(error.message);
    revalidateRecord();
    return ok("평가액을 수정했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function deleteOtherAsset(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase } = await requireUser();
    const id = str(formData.get("id"));
    if (!id) return fail("항목을 선택하세요.");
    const { error } = await supabase.from("other_assets").delete().eq("id", id);
    if (error) return fail(error.message);
    revalidateRecord();
    return ok("기타자산을 삭제했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function saveAllocationTargets(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase } = await requireUser();
    const cats = ["domestic", "overseas", "cash", "other"] as const;
    const now = new Date().toISOString();
    for (const cat of cats) {
      const pct = num(formData.get(cat));
      if (!Number.isFinite(pct) || pct < 0 || pct > 100) {
        return fail(`${cat} 목표%를 0–100으로 입력하세요.`);
      }
      const { error } = await supabase.from("allocation_targets").upsert({
        category: cat,
        target_pct: pct,
        updated_at: now,
      });
      if (error) return fail(error.message);
    }
    revalidateRecord();
    return ok("목표 배분을 저장했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function createTrade(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireUser();
    const account_id = str(formData.get("account_id"));
    const trade_type = str(formData.get("trade_type")) || "buy";
    const ticker = str(formData.get("ticker")).toUpperCase();
    const trade_date = str(formData.get("trade_date"));
    const quantity = num(formData.get("quantity"));
    const price = num(formData.get("price"));
    const fee = num(formData.get("fee"));
    const currency = str(formData.get("currency")) || "KRW";
    const reason = str(formData.get("reason")) || null;

    if (!account_id) return fail("계좌를 선택하세요.");
    if (!ticker) return fail("티커를 입력하세요.");
    if (!trade_date) return fail("일자를 입력하세요.");
    if (!Number.isFinite(quantity) || quantity <= 0) return fail("수량을 확인하세요.");
    if (!Number.isFinite(price) || price < 0) return fail("단가를 확인하세요.");

    const { error } = await supabase.from("trades").insert({
      account_id,
      trade_type,
      ticker,
      trade_date,
      quantity,
      price,
      fee: Number.isFinite(fee) ? fee : 0,
      currency,
      reason,
      created_by: user.id,
      adjust_holdings: true,
    });
    if (error) return fail(error.message);
    revalidateRecord();
    return ok("매매를 기록했습니다. 보유가 반영됩니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function createDividend(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireUser();
    const account_id = str(formData.get("account_id")) || null;
    const ticker = str(formData.get("ticker")).toUpperCase();
    const name = str(formData.get("name")) || ticker;
    const pay_date = str(formData.get("pay_date"));
    const amount = num(formData.get("amount"));
    const currency = str(formData.get("currency")) || "KRW";
    const memo = str(formData.get("memo")) || null;

    if (!ticker) return fail("티커를 입력하세요.");
    if (!pay_date) return fail("지급일을 입력하세요.");
    if (!Number.isFinite(amount) || amount <= 0) return fail("금액을 확인하세요.");

    const payload: Record<string, unknown> = {
      user_id: user.id,
      ticker,
      name,
      pay_date,
      amount,
      currency,
      memo,
    };
    if (account_id) payload.account_id = account_id;

    const { error } = await supabase.from("dividends").insert(payload);
    if (error) return fail(error.message);
    revalidateRecord();
    return ok("배당을 기록했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function createCashFlow(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireUser();
    const flow_type = str(formData.get("flow_type")) || "expense";
    const category = str(formData.get("category"));
    const amount = num(formData.get("amount"));
    const currency = str(formData.get("currency")) || "KRW";
    const flow_date = str(formData.get("flow_date"));
    const account_id = str(formData.get("account_id")) || null;
    const memo = str(formData.get("memo")) || null;

    if (!category) return fail("카테고리를 입력하세요.");
    if (!flow_date) return fail("일자를 입력하세요.");
    if (!Number.isFinite(amount) || amount <= 0) return fail("금액을 확인하세요.");

    const payload: Record<string, unknown> = {
      user_id: user.id,
      flow_type,
      category,
      amount,
      currency,
      flow_date,
      memo,
    };
    if (account_id) payload.account_id = account_id;

    const { error } = await supabase.from("cash_flows").insert(payload);
    if (error) return fail(error.message);
    revalidateRecord();
    return ok("현금흐름을 기록했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function createDebt(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireUser();
    const lender = str(formData.get("lender"));
    const debt_kind = str(formData.get("debt_kind")) || "other";
    const principal = num(formData.get("principal"));
    let original_principal = num(formData.get("original_principal"));
    const interest_rate = num(formData.get("interest_rate"));
    const due_date = str(formData.get("due_date")) || null;
    const account_id = str(formData.get("account_id")) || null;
    const memo = str(formData.get("memo")) || null;

    if (!lender) return fail("대출명/기관을 입력하세요.");
    if (!Number.isFinite(principal) || principal < 0) return fail("잔금을 확인하세요.");
    if (!Number.isFinite(original_principal) || original_principal <= 0) {
      original_principal = principal;
    }
    if (!Number.isFinite(interest_rate) || interest_rate < 0) {
      return fail("이자율을 확인하세요.");
    }

    const payload: Record<string, unknown> = {
      user_id: user.id,
      lender,
      debt_kind,
      principal,
      original_principal,
      interest_rate,
      due_date,
      memo,
    };
    if (account_id) payload.account_id = account_id;

    let { data, error } = await supabase
      .from("debts")
      .insert(payload)
      .select("id")
      .single();
    if (error && account_id) {
      delete payload.account_id;
      ({ data, error } = await supabase
        .from("debts")
        .insert(payload)
        .select("id")
        .single());
    }
    if (error) return fail(error.message);

    if (data?.id) {
      await supabase.from("debt_rate_history").insert({
        debt_id: data.id,
        user_id: user.id,
        effective_date: new Date().toISOString().slice(0, 10),
        interest_rate,
        memo: "등록 시 이자율",
      });
    }

    revalidateRecord();
    return ok("부채를 등록했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function changeDebtRate(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireUser();
    const debt_id = str(formData.get("debt_id"));
    const interest_rate = num(formData.get("interest_rate"));
    const effective_date =
      str(formData.get("effective_date")) ||
      new Date().toISOString().slice(0, 10);
    const memo = str(formData.get("memo")) || null;

    if (!debt_id) return fail("부채를 선택하세요.");
    if (!Number.isFinite(interest_rate) || interest_rate < 0) {
      return fail("이자율을 확인하세요.");
    }

    const { error: uerr } = await supabase
      .from("debts")
      .update({ interest_rate })
      .eq("id", debt_id);
    if (uerr) return fail(uerr.message);

    const { error } = await supabase.from("debt_rate_history").insert({
      debt_id,
      user_id: user.id,
      effective_date,
      interest_rate,
      memo,
    });
    if (error) return fail(error.message);
    revalidateRecord();
    return ok("이자율을 변경했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function recordDebtPayment(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireUser();
    const debt_id = str(formData.get("debt_id"));
    const amount = num(formData.get("amount"));
    const tx_date =
      str(formData.get("tx_date")) || new Date().toISOString().slice(0, 10);
    const memo = str(formData.get("memo")) || "월 원리금 납부";

    if (!debt_id) return fail("부채를 선택하세요.");
    if (!Number.isFinite(amount) || amount <= 0) return fail("납부 금액을 확인하세요.");

    const { data: debt, error: derr } = await supabase
      .from("debts")
      .select("id,principal,interest_rate")
      .eq("id", debt_id)
      .single();
    if (derr || !debt) return fail(derr?.message || "부채를 찾을 수 없습니다.");

    const bal = Number(debt.principal || 0);
    const rate = Number(debt.interest_rate || 0);
    const { interest, principal } = splitMonthlyPayment(bal, rate, amount);
    const balance_after = Math.max(bal - principal, 0);

    const { error } = await supabase.from("debt_transactions").insert({
      debt_id,
      user_id: user.id,
      tx_type: "payment",
      amount,
      tx_date,
      memo,
      interest_portion: interest,
      principal_portion: principal,
      balance_before: bal,
      balance_after,
      rate_used: rate,
    });
    if (error) return fail(error.message);
    revalidateRecord();
    return ok("납부를 기록했습니다. 잔금이 반영됩니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function adjustDebt(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireUser();
    const debt_id = str(formData.get("debt_id"));
    const tx_type = str(formData.get("tx_type")) || "repayment";
    const amount = num(formData.get("amount"));
    const tx_date =
      str(formData.get("tx_date")) || new Date().toISOString().slice(0, 10);
    const memo = str(formData.get("memo")) || null;

    if (!debt_id) return fail("부채를 선택하세요.");
    if (!["increase", "repayment"].includes(tx_type)) {
      return fail("유형을 확인하세요.");
    }
    if (!Number.isFinite(amount) || amount <= 0) return fail("금액을 확인하세요.");

    const { data: debt, error: derr } = await supabase
      .from("debts")
      .select("id,principal,interest_rate")
      .eq("id", debt_id)
      .single();
    if (derr || !debt) return fail(derr?.message || "부채를 찾을 수 없습니다.");

    const bal = Number(debt.principal || 0);
    const rate = Number(debt.interest_rate || 0);

    const { error } = await supabase.from("debt_transactions").insert({
      debt_id,
      user_id: user.id,
      tx_type,
      amount,
      tx_date,
      memo,
      principal_portion: tx_type === "repayment" ? amount : null,
      balance_before: bal,
      rate_used: rate,
    });
    if (error) return fail(error.message);
    revalidateRecord();
    return ok(
      tx_type === "increase" ? "추가 차입을 기록했습니다." : "원금 상환을 기록했습니다."
    );
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}
