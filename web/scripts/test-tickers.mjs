import assert from "node:assert/strict";
import {
  buildNameIndex,
  flowDisplayName,
  isTickerLike,
  lookupAssetName,
  normalizeKrTicker,
  tickerLookupKeys,
} from "../src/lib/tickers.ts";

assert.equal(normalizeKrTicker("00000A458730"), "458730");
assert.equal(normalizeKrTicker("A005930"), "005930");
assert.equal(normalizeKrTicker("5930"), "005930");
assert.equal(normalizeKrTicker("005930.KS"), "005930");
assert.equal(normalizeKrTicker("AAPL"), "AAPL");
assert.equal(normalizeKrTicker("0180V0"), "0180V0");

assert.equal(isTickerLike("442570"), true);
assert.equal(isTickerLike("00000A458730"), true);
assert.equal(isTickerLike("0180V0"), true);
assert.equal(isTickerLike("TIGER 미국S&P500"), false);
assert.equal(isTickerLike("삼성전자"), false);
assert.equal(isTickerLike("월급"), false);

const names = buildNameIndex([
  { ticker: "458730", name: "TIGER 미국배당다우존스" },
  { ticker: "360750", name: "TIGER 미국S&P500" },
  { ticker: "442570", name: "RISE TDF2050액티브" },
]);
assert.ok(tickerLookupKeys("458730").includes("00000A458730"));
assert.ok(tickerLookupKeys("00000A458730").includes("458730"));
assert.equal(lookupAssetName("00000A458730", names), "TIGER 미국배당다우존스");
assert.equal(lookupAssetName("458730", names), "TIGER 미국배당다우존스");
assert.equal(lookupAssetName("360750", names), "TIGER 미국S&P500");
assert.equal(lookupAssetName("0180V0", names), null);

assert.equal(
  flowDisplayName({ flow_kind: "trade", asset_ref: "360750", asset_name: "TIGER 미국S&P500" }),
  "TIGER 미국S&P500"
);
assert.equal(
  flowDisplayName({ flow_kind: "cash_flow", asset_ref: "월급" }, { cash_flow: "현금흐름" }),
  "월급"
);

console.log("tickers ok");
