import assert from "node:assert/strict";
import {
  LAST_12M,
  fillMonthSeries,
  formatMonthTick,
  lastNMonthKeys,
  monthKeysForWindow,
  monthKeysForYear,
  parseYearWindow,
  yearWindowLabel,
  yearWindowOptions,
  yearsFromMonthKeys,
} from "../src/lib/month-window.ts";
import { fmtCompactKrw } from "../src/lib/money.ts";

assert.deepEqual(lastNMonthKeys("2026-09", 12), [
  "2025-10",
  "2025-11",
  "2025-12",
  "2026-01",
  "2026-02",
  "2026-03",
  "2026-04",
  "2026-05",
  "2026-06",
  "2026-07",
  "2026-08",
  "2026-09",
]);
assert.equal(lastNMonthKeys("2026-09", 24).length, 12);

assert.deepEqual(monthKeysForYear("2026", "2026-09"), [
  "2026-01",
  "2026-02",
  "2026-03",
  "2026-04",
  "2026-05",
  "2026-06",
  "2026-07",
  "2026-08",
  "2026-09",
]);
assert.equal(monthKeysForYear("2025", "2026-09").length, 12);
assert.equal(monthKeysForYear("2025", "2026-09")[0], "2025-01");
assert.equal(monthKeysForYear("2025", "2026-09")[11], "2025-12");

assert.equal(parseYearWindow("2025", ["2025", "2026"]), "2025");
assert.equal(parseYearWindow("2024", ["2025", "2026"]), LAST_12M);
assert.equal(parseYearWindow(undefined, ["2026"]), LAST_12M);

assert.deepEqual(yearsFromMonthKeys(["2025-09", "2026-08", "2026-01"]), [
  "2025",
  "2026",
]);

const filled = fillMonthSeries(
  [
    { month: "2026-08", value: 100 },
    { month: "2026-08", value: 20 },
  ],
  ["2026-07", "2026-08"]
);
assert.deepEqual(filled, [
  { month: "2026-07", value: 0 },
  { month: "2026-08", value: 120 },
]);

assert.equal(formatMonthTick("2025-09", LAST_12M), "25.09");
assert.equal(formatMonthTick("2026-01", "2026"), "1월");
assert.equal(yearWindowLabel(LAST_12M), "최근 12개월");
assert.equal(yearWindowLabel("2026"), "2026년");
assert.equal(yearWindowOptions(["2025", "2026"]).length, 3);

assert.equal(monthKeysForWindow(LAST_12M, "2026-09").length, 12);
assert.equal(monthKeysForWindow("2026", "2026-09").length, 9);

assert.equal(fmtCompactKrw(282158), "28만");
assert.equal(fmtCompactKrw(34800), "3.5만");
assert.equal(fmtCompactKrw(500), "500");
assert.equal(fmtCompactKrw(1_200_000_000), "12억");

console.log("month-window ok");
