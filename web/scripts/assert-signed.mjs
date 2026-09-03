import assert from "node:assert/strict";
import {
  fmtPctArrow,
  retTone,
  signedArrow,
  signedTone,
} from "../src/lib/money.ts";

assert.equal(signedTone(11610), "up");
assert.equal(signedTone(-500), "down");
assert.equal(signedTone(0), "flat");
assert.equal(signedTone(null), "flat");
assert.equal(signedArrow("up"), "↑");
assert.equal(signedArrow("down"), "↓");
assert.equal(signedArrow("flat"), "");
assert.equal(fmtPctArrow(12.34), "↑ 12.34%");
assert.equal(fmtPctArrow(-3.5), "↓ 3.50%");
assert.equal(fmtPctArrow(0), "0.00%");
assert.equal(retTone(0.04), "flat");
assert.equal(retTone(1.2), "up");
assert.equal(retTone(-2), "down");

console.log("signed display helpers ok");
