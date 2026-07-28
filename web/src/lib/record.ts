export const ASSET_KIND_OPTIONS = [
  { value: "real_estate", label: "부동산" },
  { value: "pension", label: "연금" },
  { value: "insurance", label: "보험" },
  { value: "deposit", label: "예적금" },
  { value: "crypto", label: "암호화폐" },
  { value: "other", label: "기타" },
] as const;

export const OWNERSHIP_OPTIONS = [
  { value: "joint", label: "공동" },
  { value: "mine", label: "나" },
  { value: "spouse", label: "배우자" },
] as const;

export const DEBT_KIND_OPTIONS = [
  { value: "mortgage", label: "주택담보" },
  { value: "jeonse", label: "전세자금" },
  { value: "credit", label: "신용" },
  { value: "card", label: "카드" },
  { value: "student", label: "학자금" },
  { value: "other", label: "기타" },
] as const;

export const ACCOUNT_TYPE_OPTIONS = [
  { value: "brokerage", label: "증권" },
  { value: "bank", label: "은행" },
  { value: "loan", label: "대출" },
] as const;

export const INCOME_CATEGORIES = [
  "월급",
  "사업소득",
  "이자",
  "증권입금",
  "예수금이자",
  "기타수입",
] as const;

export const EXPENSE_CATEGORIES = [
  "생활비",
  "주거",
  "식비",
  "교통",
  "보험",
  "세금납부",
  "이체/저축",
  "증권출금",
  "기타지출",
] as const;

export function splitMonthlyPayment(
  balance: number,
  annualRatePct: number,
  payment: number
): { interest: number; principal: number } {
  const bal = Math.max(0, Number(balance) || 0);
  const pay = Math.max(0, Number(payment) || 0);
  const interest = Math.round((bal * (Number(annualRatePct) || 0)) / 100 / 12);
  if (pay <= interest) {
    return { interest: pay, principal: 0 };
  }
  const principal = Math.min(bal, pay - interest);
  return { interest, principal };
}

export type ActionResult = { ok: true; message: string } | { ok: false; message: string };
