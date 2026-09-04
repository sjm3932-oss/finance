import assert from "node:assert/strict";
import {
  LAST_12M,
  fillMonthSeries,
  formatMonthTick,
  lastNMonthKeys,
  monthInPeriod,
  monthKeysForPeriod,
  monthKeysForYear,
  parsePeriodWindow,
  periodLabel,
  periodOptions,
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
assert.deepEqual(lastNMonthKeys("2026-09", 1), ["2026-09"]);
assert.equal(lastNMonthKeys("2026-09", 3).length, 3);
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

assert.equal(parsePeriodWindow("3m", ["2025", "2026"]), "3m");
assert.equal(parsePeriodWindow("ytd", ["2026"]), "ytd");
assert.equal(parsePeriodWindow("2025", ["2025", "2026"]), "2025");
assert.equal(parsePeriodWindow("2024", ["2025", "2026"]), LAST_12M);
assert.equal(parsePeriodWindow(undefined, ["2026"]), LAST_12M);

assert.deepEqual(monthKeysForPeriod("1m", "2026-09"), ["2026-09"]);
assert.deepEqual(monthKeysForPeriod("ytd", "2026-09"), monthKeysForYear("2026", "2026-09"));
assert.equal(monthKeysForPeriod("6m", "2026-09").length, 6);

assert.equal(monthInPeriod("2026-09-04", ["2026-09"]), true);
assert.equal(monthInPeriod("2026-08-31", ["2026-09"]), false);

assert.equal(formatMonthTick("2025-09", true), "25.09");
assert.equal(formatMonthTick("2026-01", false), "1월");
assert.equal(periodLabel(LAST_12M, "2026-09"), "최근 12개월");
assert.equal(periodLabel("ytd", "2026-09"), "2026년");
assert.equal(periodLabel("1m", "2026-09"), "이번 달");

const opts = periodOptions(["2025", "2026"], "2026-09");
assert.ok(opts.some((o) => o.id === "1m"));
assert.ok(opts.some((o) => o.id === "ytd" && o.label === "올해"));
assert.ok(opts.some((o) => o.id === "2025"));
assert.ok(!opts.some((o) => o.id === "2026"));

assert.deepEqual(yearsFromMonthKeys(["2025-09", "2026-08"]), ["2025", "2026"]);

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

assert.equal(fmtCompactKrw(282158), "28만");
assert.equal(fmtCompactKrw(34800), "3.5만");
assert.equal(fmtCompactKrw(500), "500");
assert.equal(fmtCompactKrw(1_200_000_000), "12억");

console.log("month-window ok");
