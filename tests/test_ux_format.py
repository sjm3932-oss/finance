"""Tests for UX money formatting."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "streamlit_app"))

from lib.ui_ko import (  # noqa: E402
    format_money_columns,
    format_money_value,
    is_money_column,
)
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


def test_format_money_value_commas():
    assert format_money_value(1_234_567) == "1,234,567"
    assert format_money_value(-1000) == "-1,000"
    assert format_money_value(12.5) == "12.50"
    assert format_money_value(None) == "—"
    assert format_money_value("₩1,000") == "₩1,000"


def test_format_money_columns_table():
    df = pd.DataFrame(
        {
            "종목": ["A", "B"],
            "금액": [1_500_000, -2000],
            "수량": [10, 3],
            "이자율(%)": [3.5, 4.0],
        }
    )
    out = format_money_columns(df)
    assert out["금액"].tolist() == ["1,500,000", "-2,000"]
    assert out["수량"].tolist() == [10, 3]
    assert out["이자율(%)"].tolist() == [3.5, 4.0]


def test_is_money_column():
    assert is_money_column("금액")
    assert is_money_column("실현손익")
    assert is_money_column("amount")
    assert not is_money_column("수량")
    assert not is_money_column("이자율(%)")
    assert not is_money_column("수익률(%)")
