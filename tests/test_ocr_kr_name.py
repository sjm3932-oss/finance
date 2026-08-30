"""Name agreement used to detect OCR ticker/name mismatches."""

from __future__ import annotations

import unittest


def norm_name(raw: str) -> str:
    return "".join(str(raw or "").split()).replace("적격", "").lower()


def names_agree(a: str, b: str) -> bool:
    x, y = norm_name(a), norm_name(b)
    if not x or not y:
        return False
    return x == y or x in y or y in x


class NameAgreeTests(unittest.TestCase):
    def test_rise_not_tiger(self):
        self.assertFalse(
            names_agree("RISE TDF2050액티브 적격", "TIGER 미국S&P500")
        )

    def test_exact_after_strip(self):
        self.assertTrue(
            names_agree("RISE TDF2050액티브 적격", "RISE TDF2050액티브")
        )

    def test_tiger_sp_not_nasdaq(self):
        self.assertFalse(names_agree("TIGER 미국S&P500", "TIGER 미국나스닥100"))


if __name__ == "__main__":
    unittest.main()
