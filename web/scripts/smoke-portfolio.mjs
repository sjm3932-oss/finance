/**
 * Minimal portfolio math smoke (no TS build required).
 */
function toKrw(amount, ccy, usdkrw) {
  if ((ccy || "KRW").toUpperCase() === "USD") return usdkrw ? amount * usdkrw : 0;
  return amount;
}

const qty = 10;
const avg = 70000;
const price = 80000;
const value = price * qty;
const invest = toKrw(value, "KRW", 1300);
const cash = 1_000_000;
const deposits = 5_000_000;
const other = 50_000_000;
const debt = 10_000_000;
const net = invest + cash + deposits + other - debt;

if (invest !== 800_000) throw new Error("invest");
if (net !== 46_800_000) throw new Error("net");

function institutionsForOwnership(accounts, ownership) {
  const own = ["joint", "mine", "spouse"].includes(ownership) ? ownership : null;
  const set = new Set();
  for (const a of accounts) {
    if (own && (a.ownership || "joint") !== own) continue;
    set.add(a.institution || "계좌");
  }
  return [...set].sort((a, b) => a.localeCompare(b, "ko"));
}

const brokerAccounts = [
  { institution: "신한투자증권", ownership: "mine" },
  { institution: "토스증권", ownership: "mine" },
  { institution: "한국투자증권", ownership: "mine" },
];
const mineInst = institutionsForOwnership(brokerAccounts, "mine").join(",");
if (mineInst !== "신한투자증권,토스증권,한국투자증권") {
  throw new Error("mine children: " + mineInst);
}
if (institutionsForOwnership(brokerAccounts, "joint").length !== 0) {
  throw new Error("joint should have no institutions");
}
if (institutionsForOwnership(brokerAccounts, "spouse").length !== 0) {
  throw new Error("spouse should have no institutions");
}

console.log("web portfolio smoke ok", { invest, net, deposits, mineInst });

function otherAssetReturn(row) {
  const value = Number(row.value_krw || 0);
  const costRaw = Number(row.cost_krw);
  const cost = Number.isFinite(costRaw) && costRaw > 0 ? costRaw : null;
  if (cost === null) return { cost: null, value, pnl: null, pct: null };
  const pnl = value - cost;
  return { cost, value, pnl, pct: (100 * pnl) / cost };
}
const re = otherAssetReturn({ cost_krw: 800_000_000, value_krw: 880_000_000 });
if (re.pnl !== 80_000_000) throw new Error("other pnl");
if (Math.abs(re.pct - 10) > 1e-9) throw new Error("other pct " + re.pct);
if (otherAssetReturn({ value_krw: 1 }).pct !== null) throw new Error("no cost");

function parseIsoDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || "").trim());
  if (!m) return null;
  return [Number(m[1]), Number(m[2]), Number(m[3])];
}
function calendarMonthsBetween(fromIso, toIso) {
  const a = parseIsoDate(fromIso);
  const b = parseIsoDate(toIso);
  if (!a || !b) return 0;
  let months = (b[0] - a[0]) * 12 + (b[1] - a[1]);
  if (b[2] < a[2]) months -= 1;
  return Math.max(0, months);
}
function isMonthlyDeposit(kind) {
  return kind === "installment" || kind === "subscription";
}
function installmentPaymentsMade(start, maturity, hasMaturity, cap, asOf) {
  if (asOf < start) return 0;
  const until = hasMaturity && maturity < asOf ? maturity : asOf;
  return Math.min(cap, calendarMonthsBetween(start, until) + 1);
}
function installmentProgress(d, asOf) {
  if (!isMonthlyDeposit(d.deposit_kind)) return null;
  const monthly = Number(d.monthly_amount || 0);
  if (!(monthly > 0)) return null;
  const start = d.start_date ? String(d.start_date).slice(0, 10) : "";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(start)) return null;
  const maturity = d.maturity_date ? String(d.maturity_date).slice(0, 10) : "";
  const hasMaturity = /^\d{4}-\d{2}-\d{2}$/.test(maturity);
  const total = hasMaturity ? Math.max(1, calendarMonthsBetween(start, maturity)) : 0;
  const cap = total > 0 ? total : 1200;
  const made = installmentPaymentsMade(start, maturity, hasMaturity, cap, asOf);
  const rate = Number(d.interest_rate || 0) / 100;
  const formulaInterest = Math.round(
    (monthly * (rate / 12) * (made * Math.max(made - 1, 0))) / 2
  );
  const n = total > 0 ? total : made;
  const maturityInterest = Math.round((monthly * rate * n * (n + 1)) / 24);
  const seed = Number(d.current_value || 0);
  const seedOnRaw = d.balance_as_of ? String(d.balance_as_of).slice(0, 10) : "";
  const seedOn = /^\d{4}-\d{2}-\d{2}$/.test(seedOnRaw) ? seedOnRaw : asOf;
  const useSeed = seed > 0 && asOf >= seedOn;
  let extraPayments = 0;
  let value = monthly * made + formulaInterest;
  let interest = formulaInterest;
  if (useSeed) {
    extraPayments = Math.max(
      0,
      made - installmentPaymentsMade(start, maturity, hasMaturity, cap, seedOn)
    );
    const extraInterest = Math.round(
      (monthly * (rate / 12) * (extraPayments * Math.max(extraPayments - 1, 0))) / 2
    );
    value = seed + monthly * extraPayments + extraInterest;
    interest = extraInterest;
  }
  return {
    paymentsMade: made,
    paymentsTotal: n,
    interest,
    value,
    maturityInterest: useSeed ? 0 : maturityInterest,
    maturityValue: useSeed
      ? value + monthly * Math.max(0, n - made)
      : monthly * n + maturityInterest,
    seeded: useSeed,
    extraPayments,
  };
}
function depositBalance(d, asOf) {
  const prog = installmentProgress(d, asOf);
  if (prog) return prog.value;
  const cur = Number(d.current_value);
  if (Number.isFinite(cur) && cur > 0) return cur;
  return Number(d.principal || 0);
}
function calendarDaysBetween(fromIso, toIso) {
  const [y1, m1, d1] = fromIso.split("-").map(Number);
  const [y2, m2, d2] = toIso.split("-").map(Number);
  return Math.round((Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / 86400000);
}
function depositExpectedInterest(d, asOf = "2026-04-15") {
  const prog = installmentProgress(d, asOf);
  if (prog) return prog.maturityInterest;
  const principal = Number(d.principal || 0);
  const rate = Number(d.interest_rate || 0);
  if (!(principal > 0) || !(rate > 0)) return null;
  const start = d.start_date ? String(d.start_date).slice(0, 10) : null;
  const maturity = d.maturity_date ? String(d.maturity_date).slice(0, 10) : null;
  const days = start && maturity ? Math.max(0, calendarDaysBetween(start, maturity)) : 365;
  return Math.round(principal * (rate / 100) * (days / 365));
}
if (depositBalance({ principal: 10_000_000, current_value: 0 }) !== 10_000_000) {
  throw new Error("deposit fallback");
}
const interest = depositExpectedInterest({
  principal: 10_000_000,
  interest_rate: 3.65,
  start_date: "2026-01-01",
  maturity_date: "2027-01-01",
});
if (interest !== 365_000) throw new Error("deposit interest " + interest);

const sav = {
  deposit_kind: "installment",
  monthly_amount: 100_000,
  interest_rate: 3.6,
  start_date: "2026-01-15",
  maturity_date: "2027-01-15",
};
const p1 = installmentProgress(sav, "2026-01-15");
if (!p1 || p1.paymentsMade !== 1 || p1.value !== 100_000) {
  throw new Error("installment month 1 " + JSON.stringify(p1));
}
const p4 = installmentProgress(sav, "2026-04-15");
if (!p4 || p4.paymentsMade !== 4 || p4.interest !== 1_800 || p4.value !== 401_800) {
  throw new Error("installment month 4 " + JSON.stringify(p4));
}
const pBeforePay = installmentProgress(sav, "2026-04-14");
if (!pBeforePay || pBeforePay.paymentsMade !== 3) {
  throw new Error("installment waits for payday " + JSON.stringify(pBeforePay));
}
const pMat = installmentProgress(sav, "2027-01-15");
if (!pMat || pMat.paymentsMade !== 12 || pMat.maturityInterest !== 23_400) {
  throw new Error("installment maturity " + JSON.stringify(pMat));
}
if (depositBalance(sav, "2026-04-15") !== 401_800) {
  throw new Error("installment live balance");
}
if (depositExpectedInterest(sav) !== 23_400) {
  throw new Error("installment expected interest " + depositExpectedInterest(sav));
}

const existing = {
  ...sav,
  current_value: 2_000_000,
  balance_as_of: "2026-04-15",
};
const seededNow = installmentProgress(existing, "2026-04-15");
if (!seededNow || seededNow.value !== 2_000_000 || !seededNow.seeded) {
  throw new Error("existing seed today " + JSON.stringify(seededNow));
}
const seededNext = installmentProgress(existing, "2026-05-15");
if (!seededNext || seededNext.extraPayments !== 1 || seededNext.value !== 2_100_000) {
  throw new Error("existing seed next month " + JSON.stringify(seededNext));
}
