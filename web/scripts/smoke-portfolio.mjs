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
const other = 50_000_000;
const debt = 10_000_000;
const net = invest + cash + other - debt;

if (invest !== 800_000) throw new Error("invest");
if (net !== 41_800_000) throw new Error("net");

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

console.log("web portfolio smoke ok", { invest, net, mineInst });

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
