import assert from "node:assert/strict";
import { fmtKrw, fmtMoney, toLedgerMoney } from "../src/lib/money.ts";

const USDKRW = 1351;

// Yahoo/Toss US ETF dividends are stored in USD. The ledger used to format
// the native $ amount as ₩ (TSLY $8.24 → ₩8). Convert first, then format KRW.
const tsly = toLedgerMoney(8.24, "USD", USDKRW);
assert.equal(tsly.currency, "KRW");
assert.equal(Math.round(tsly.amount), 11132);
assert.equal(fmtMoney(tsly.amount, tsly.currency), "₩11,132");
assert.notEqual(fmtMoney(8.24), "₩11,132");
assert.equal(fmtMoney(8.24), "₩8");

const nvdy = toLedgerMoney(4.8, "USD", USDKRW);
assert.equal(Math.round(nvdy.amount), 6485);
assert.equal(fmtMoney(nvdy.amount, nvdy.currency), "₩6,485");

const goow = toLedgerMoney(9.2646, "USD", USDKRW);
assert.equal(Math.round(goow.amount), 12516);
assert.equal(fmtMoney(goow.amount, goow.currency), "₩12,516");

const tiger = toLedgerMoney(11610, "KRW", USDKRW);
assert.equal(tiger.amount, 11610);
assert.equal(tiger.currency, "KRW");
assert.equal(fmtKrw(tiger.amount), "₩11,610");

const noFx = toLedgerMoney(8.24, "USD", null);
assert.equal(noFx.currency, "USD");
assert.equal(noFx.amount, 8.24);
assert.equal(fmtMoney(noFx.amount, noFx.currency), "$8.24");

console.log("ledger-money ok");
