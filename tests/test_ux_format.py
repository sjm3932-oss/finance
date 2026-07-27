"""Tests for UX money formatting."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "streamlit_app"))

from lib.ux import fmt_krw, ret_class  # noqa: E402


def test_fmt_krw_full():
    assert fmt_krw(1_234_567, abbreviate=False) == "₩1,234,567"
    assert fmt_krw(-1000, signed=True, abbreviate=False) == "-₩1,000"
    assert fmt_krw(500, signed=True, abbreviate=False) == "+₩500"


def test_fmt_krw_abbrev():
    assert "억" in fmt_krw(250_000_000, abbreviate=True)
    assert "만" in fmt_krw(340_000, abbreviate=True)


def test_ret_class():
    assert ret_class(1.2) == "up"
    assert ret_class(-2.0) == "down"
    assert ret_class(0.0) == "flat"
