"""Ticker → 종목명 display helpers for the transaction ledger."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "streamlit_app"))

from lib.ticker_names import (  # noqa: E402
    build_name_index,
    flow_display_name,
    is_ticker_like,
    lookup_asset_name,
    normalize_kr_ticker,
)


def test_normalize_padded_kis_codes():
    assert normalize_kr_ticker("00000A458730") == "458730"
    assert normalize_kr_ticker("A005930") == "005930"
    assert normalize_kr_ticker("5930") == "005930"
    assert normalize_kr_ticker("AAPL") == "AAPL"
    assert normalize_kr_ticker("0180V0") == "0180V0"


def test_is_ticker_like():
    assert is_ticker_like("442570")
    assert is_ticker_like("00000A458730")
    assert is_ticker_like("0180V0")
    assert not is_ticker_like("TIGER 미국S&P500")
    assert not is_ticker_like("삼성전자")
    assert not is_ticker_like("월급")


def test_lookup_matches_padded_ticker_to_holding_name():
    names = build_name_index(
        [
            {"ticker": "458730", "name": "TIGER 미국배당다우존스"},
            {"ticker": "360750", "name": "TIGER 미국S&P500"},
            {"ticker": "442570", "name": "RISE TDF2050액티브"},
        ]
    )
    assert lookup_asset_name("00000A458730", names) == "TIGER 미국배당다우존스"
    assert lookup_asset_name("458730", names) == "TIGER 미국배당다우존스"
    assert lookup_asset_name("360750", names) == "TIGER 미국S&P500"
    assert lookup_asset_name("0180V0", names) is None


def test_flow_display_prefers_name():
    assert (
        flow_display_name("trade", "360750", "TIGER 미국S&P500")
        == "TIGER 미국S&P500"
    )
    assert flow_display_name("cash_flow", "월급", None) == "월급"
    assert flow_display_name("trade", None, None, kind_ko={"trade": "매매"}) == "매매"
