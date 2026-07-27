"""Unit tests for portfolio insight helpers (no DB)."""

from __future__ import annotations

import pandas as pd

from lib.portfolio_insights import allocation_frames, dividend_stats, market_region


def test_market_region_kr_ticker():
    assert market_region("005930", "KRW") == "국내"
    assert market_region("AAPL", "USD") == "해외"


def test_allocation_frames_sums():
    rows = [
        {
            "ticker": "005930",
            "name": "삼성전자",
            "value": 1000000,
            "ccy": "KRW",
            "institution": "키움",
        },
        {
            "ticker": "AAPL",
            "name": "Apple",
            "value": 100,
            "ccy": "USD",
            "institution": "토스",
        },
        {
            "ticker": "005930",
            "name": "삼성전자",
            "value": 500000,
            "ccy": "KRW",
            "institution": "토스",
        },
    ]
    by_t, by_r, by_a = allocation_frames(rows, usdkrw=1000.0)
    assert abs(by_t[by_t["ticker"] == "005930"]["value_krw"].sum() - 1_500_000) < 1
    assert abs(by_t[by_t["ticker"] == "AAPL"]["value_krw"].sum() - 100_000) < 1
    assert set(by_r["label"]) == {"국내", "해외"}
    assert set(by_a["label"]) == {"키움", "토스"}


def test_dividend_stats_empty():
    stats = dividend_stats(pd.DataFrame(), None)
    assert stats["month_krw"] == 0.0
    assert stats["expected_krw"] == 0.0
