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

function depositBalance(d) {
  const cur = Number(d.current_value);
  if (Number.isFinite(cur) && cur > 0) return cur;
  return Number(d.principal || 0);
}
function calendarDaysBetween(fromIso, toIso) {
  const [y1, m1, d1] = fromIso.split("-").map(Number);
  const [y2, m2, d2] = toIso.split("-").map(Number);
  return Math.round((Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / 86400000);
}
function depositExpectedInterest(d) {
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
