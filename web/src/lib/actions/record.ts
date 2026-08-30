"use server";

import { revalidatePath } from "next/cache";
import { requireAllowedUser } from "@/lib/actions/auth";
import { todayKst } from "@/lib/dates";
import { splitMonthlyPayment, type ActionResult } from "@/lib/record";

function humanizeDbError(message: string): string {
  const m = message.toLowerCase();
  if (m.includes("duplicate") || m.includes("unique")) {
    return "이미 같은 데이터가 있습니다.";
  }
  if (m.includes("foreign key") || m.includes("violates")) {
    return "연결된 계좌/항목을 확인하세요.";
  }
  if (m.includes("permission") || m.includes("rls") || m.includes("policy")) {
    return "저장 권한이 없습니다. 로그인 상태를 확인하세요.";
  }
  if (m.includes("oversell") || m.includes("insufficient")) {
    return "매도 수량이 보유보다 많습니다.";
  }
  if (m.includes("jwt") || m.includes("auth")) {
    return "로그인이 만료되었습니다. 다시 로그인해 주세요.";
  }
  // Keep short original if already Korean-ish, else generic
  if (/[가-힣]/.test(message)) return message;
  return "저장에 실패했습니다. 입력값을 확인한 뒤 다시 시도하세요.";
}

function fail(message: string): ActionResult {
  return { ok: false, message };
}

function ok(message: string): ActionResult {
  return { ok: true, message };
}

function dbFail(error: { message: string } | null): ActionResult {
  return fail(humanizeDbError(error?.message || "저장 실패"));
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
  revalidatePath("/pnl");
  revalidatePath("/flows");
  revalidatePath("/more/net-worth");
  revalidatePath("/more/other-assets");
  revalidatePath("/more/debts");
}

export async function createAccount(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireAllowedUser();
    const institution = str(formData.get("institution"));
    const account_type = str(formData.get("account_type")) || "brokerage";
    const currency = str(formData.get("currency")).toUpperCase() || "KRW";
    const ownership = str(formData.get("ownership")) || "mine";
    const cashRaw = str(formData.get("cash_balance"));
    const cash_balance = cashRaw === "" ? 0 : num(formData.get("cash_balance"));
    const memo = str(formData.get("memo")) || null;

    if (!institution) return fail("금융기관 이름을 입력하세요.");
    if (!/^[A-Z]{3}$/.test(currency)) {
      return fail("통화는 KRW, USD처럼 3글자 코드로 입력하세요.");
    }
    if (!Number.isFinite(cash_balance) || cash_balance < 0) {
      return fail("현금 잔고를 확인하세요.");
    }

    const payload: Record<string, unknown> = {
      user_id: user.id,
      institution,
      account_type,
      currency,
      ownership,
      cash_balance,
      memo,
    };

    let { error } = await supabase.from("accounts").insert(payload);
    // Older schemas may lack cash/ownership/memo columns — retry lean insert.
    if (error) {
      ({ error } = await supabase.from("accounts").insert({
        user_id: user.id,
        institution,
        account_type,
        currency,
        ownership,
        cash_balance,
      }));
    }
    if (error) {
      ({ error } = await supabase.from("accounts").insert({
        user_id: user.id,
        institution,
        account_type,
        currency,
      }));
    }
    if (error) return dbFail(error);
    revalidateRecord();
    return ok(`${institution} (${currency}) 계좌를 추가했습니다.`);
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function updateAccountCash(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase } = await requireAllowedUser();
    const id = str(formData.get("account_id"));
    const cash_balance = num(formData.get("cash_balance"));
    const ownership = str(formData.get("ownership")) || "mine";
    if (!id) return fail("계좌를 선택하세요.");
    if (!Number.isFinite(cash_balance) || cash_balance < 0) {
      return fail("현금 잔고를 확인하세요.");
    }

    const { error } = await supabase
      .from("accounts")
      .update({ cash_balance, ownership })
      .eq("id", id);
    if (error) return dbFail(error);
    revalidateRecord();
    return ok("계좌 현금·소유를 저장했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

const ACCOUNT_TYPES = new Set(["brokerage", "bank", "loan"]);
const OWNERSHIPS = new Set(["joint", "mine", "spouse"]);

export async function updateAccount(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase } = await requireAllowedUser();
    const id = str(formData.get("account_id"));
    const institution = str(formData.get("institution"));
    const account_type = str(formData.get("account_type")) || "brokerage";
    const currency = str(formData.get("currency")).toUpperCase() || "KRW";
    const ownership = str(formData.get("ownership")) || "mine";
    const cashRaw = str(formData.get("cash_balance"));
    const cash_balance = cashRaw === "" ? 0 : num(formData.get("cash_balance"));
    const memo = str(formData.get("memo")) || null;

    if (!id) return fail("계좌를 선택하세요.");
    if (!institution) return fail("금융기관 이름을 입력하세요.");
    if (!ACCOUNT_TYPES.has(account_type)) return fail("계좌유형을 확인하세요.");
    if (!OWNERSHIPS.has(ownership)) return fail("소유를 확인하세요.");
    if (!/^[A-Z]{3}$/.test(currency)) {
      return fail("통화는 KRW, USD처럼 3글자 코드로 입력하세요.");
    }
    if (!Number.isFinite(cash_balance) || cash_balance < 0) {
      return fail("현금 잔고를 확인하세요.");
    }

    const payload: Record<string, unknown> = {
      institution,
      account_type,
      currency,
      ownership,
      cash_balance,
      memo,
    };
    let { error } = await supabase.from("accounts").update(payload).eq("id", id);
    if (error) {
      ({ error } = await supabase
        .from("accounts")
        .update({ institution, account_type, currency, ownership, cash_balance })
        .eq("id", id));
    }
    if (error) {
      ({ error } = await supabase
        .from("accounts")
        .update({ institution, account_type, currency })
        .eq("id", id));
    }
    if (error) return dbFail(error);
    revalidateRecord();
    return ok(`${institution} (${currency}) 계좌를 저장했습니다.`);
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function deleteAccount(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase } = await requireAllowedUser();
    const id = str(formData.get("account_id"));
    if (!id) return fail("계좌를 선택하세요.");
    const { error } = await supabase.from("accounts").delete().eq("id", id);
    if (error) return dbFail(error);
    revalidateRecord();
    return ok("계좌와 연결된 보유·매매를 삭제했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function createOtherAsset(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireAllowedUser();
    const name = str(formData.get("name"));
    const asset_kind = str(formData.get("asset_kind")) || "other";
    const value_krw = num(formData.get("value_krw"));
    const costRaw = str(formData.get("cost_krw"));
    const cost_krw = costRaw === "" ? null : num(formData.get("cost_krw"));
    const ownership = str(formData.get("ownership")) || "joint";
    const memo = str(formData.get("memo")) || null;
    if (!name) return fail("이름을 입력하세요.");
    if (!Number.isFinite(value_krw) || value_krw < 0) {
      return fail("현재 시세를 확인하세요.");
    }
    if (cost_krw !== null && (!Number.isFinite(cost_krw) || cost_krw < 0)) {
      return fail("매수가를 확인하세요.");
    }

    const payload: Record<string, unknown> = {
      user_id: user.id,
      name,
      asset_kind,
      value_krw,
      cost_krw,
      ownership,
      memo,
      updated_at: new Date().toISOString(),
    };
    let { error } = await supabase.from("other_assets").insert(payload);
    if (error) {
      delete payload.cost_krw;
      ({ error } = await supabase.from("other_assets").insert(payload));
    }
    if (error) return dbFail(error);
    revalidateRecord();
    return ok("기타자산을 추가했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function updateOtherAssetValue(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase } = await requireAllowedUser();
    const id = str(formData.get("id"));
    const value_krw = num(formData.get("value_krw"));
    const costRaw = str(formData.get("cost_krw"));
    const cost_krw = costRaw === "" ? null : num(formData.get("cost_krw"));
    if (!id) return fail("항목을 선택하세요.");
    if (!Number.isFinite(value_krw) || value_krw < 0) {
      return fail("현재 시세를 확인하세요.");
    }
    if (cost_krw !== null && (!Number.isFinite(cost_krw) || cost_krw < 0)) {
      return fail("매수가를 확인하세요.");
    }

    let { error } = await supabase
      .from("other_assets")
      .update({ value_krw, cost_krw, updated_at: new Date().toISOString() })
      .eq("id", id);
    if (error) {
      ({ error } = await supabase
        .from("other_assets")
        .update({ value_krw, updated_at: new Date().toISOString() })
        .eq("id", id));
    }
    if (error) return dbFail(error);
    revalidateRecord();
    return ok("매수가·시세를 저장했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function deleteOtherAsset(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase } = await requireAllowedUser();
    const id = str(formData.get("id"));
    if (!id) return fail("항목을 선택하세요.");
    const { error } = await supabase.from("other_assets").delete().eq("id", id);
    if (error) return dbFail(error);
    revalidateRecord();
    return ok("기타자산을 삭제했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function createTrade(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireAllowedUser();
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
    if (error) return dbFail(error);
    revalidateRecord();
    return ok("매매를 기록했습니다. 보유가 반영됩니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function createDividend(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireAllowedUser();
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
    if (error) return dbFail(error);
    revalidateRecord();
    return ok("배당을 기록했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function createCashFlow(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireAllowedUser();
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
    if (error) return dbFail(error);
    revalidateRecord();
    return ok("현금흐름을 기록했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function createDebt(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireAllowedUser();
    const lender = str(formData.get("lender"));
    const debt_kind = str(formData.get("debt_kind")) || "other";
    const principal = num(formData.get("principal"));
    let original_principal = num(formData.get("original_principal"));
    const interest_rate = num(formData.get("interest_rate"));
    const due_date = str(formData.get("due_date")) || null;
    const account_id = str(formData.get("account_id")) || null;
    const ownership = str(formData.get("ownership")) || "joint";
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
      ownership,
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
    if (error) return dbFail(error);

    if (data?.id) {
      await supabase.from("debt_rate_history").insert({
        debt_id: data.id,
        user_id: user.id,
        effective_date: todayKst(),
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
    const { supabase, user } = await requireAllowedUser();
    const debt_id = str(formData.get("debt_id"));
    const interest_rate = num(formData.get("interest_rate"));
    const effective_date =
      str(formData.get("effective_date")) ||
      todayKst();
    const memo = str(formData.get("memo")) || null;

    if (!debt_id) return fail("부채를 선택하세요.");
    if (!Number.isFinite(interest_rate) || interest_rate < 0) {
      return fail("이자율을 확인하세요.");
    }

    const { error: uerr } = await supabase
      .from("debts")
      .update({ interest_rate })
      .eq("id", debt_id);
    if (uerr) return dbFail(uerr);

    const { error } = await supabase.from("debt_rate_history").insert({
      debt_id,
      user_id: user.id,
      effective_date,
      interest_rate,
      memo,
    });
    if (error) return dbFail(error);
    revalidateRecord();
    return ok("이자율을 변경했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function recordDebtPayment(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireAllowedUser();
    const debt_id = str(formData.get("debt_id"));
    const amount = num(formData.get("amount"));
    const tx_date =
      str(formData.get("tx_date")) || todayKst();
    const memo = str(formData.get("memo")) || "월 원리금 납부";

    if (!debt_id) return fail("부채를 선택하세요.");
    if (!Number.isFinite(amount) || amount <= 0) return fail("납부 금액을 확인하세요.");

    const { data: debt, error: derr } = await supabase
      .from("debts")
      .select("id,principal,interest_rate")
      .eq("id", debt_id)
      .single();
    if (derr || !debt) return fail(derr ? humanizeDbError(derr.message) : "부채를 찾을 수 없습니다.");

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
    if (error) return dbFail(error);
    revalidateRecord();
    return ok("납부를 기록했습니다. 잔금이 반영됩니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}

export async function adjustDebt(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireAllowedUser();
    const debt_id = str(formData.get("debt_id"));
    const tx_type = str(formData.get("tx_type")) || "repayment";
    const amount = num(formData.get("amount"));
    const tx_date =
      str(formData.get("tx_date")) || todayKst();
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
    if (derr || !debt) return fail(derr ? humanizeDbError(derr.message) : "부채를 찾을 수 없습니다.");

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
    if (error) return dbFail(error);
    revalidateRecord();
    return ok(
      tx_type === "increase" ? "추가 차입을 기록했습니다." : "원금 상환을 기록했습니다."
    );
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패했습니다.");
  }
}
