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
console.log("web portfolio smoke ok", { invest, net });
