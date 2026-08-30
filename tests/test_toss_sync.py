"""Tests for Toss holdings mapping (no live API)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from toss_client import (  # noqa: E402
    holdings_by_currency,
    humanize_toss_error,
    map_holding,
    normalize_ticker,
)


def test_normalize_kr_ticker():
    assert normalize_ticker("5930", "KR") == "005930"
    assert normalize_ticker("005930.KS") == "005930"


def test_map_holding_kr_and_us():
    kr = map_holding(
        {
            "symbol": "005930",
            "name": "삼성전자",
            "marketCountry": "KR",
            "currency": "KRW",
            "quantity": "100",
            "lastPrice": "72000",
            "averagePurchasePrice": "65000",
        }
    )
    assert kr == {
        "ticker": "005930",
        "name": "삼성전자",
        "quantity": 100.0,
        "avg_price": 65000.0,
        "currency": "KRW",
        "last_price": 72000.0,
    }
    us = map_holding(
        {
            "symbol": "AAPL",
            "name": "Apple",
            "marketCountry": "US",
            "currency": "USD",
            "quantity": "1.5",
            "lastPrice": "210.1",
            "averagePurchasePrice": "185",
        }
    )
    assert us["ticker"] == "AAPL"
    assert us["quantity"] == 1.5
    assert us["currency"] == "USD"


def test_skip_zero_qty():
    assert map_holding({"symbol": "AAPL", "quantity": "0"}) is None


def test_split_by_currency():
    grouped = holdings_by_currency(
        [
            {
                "symbol": "005930",
                "name": "삼성전자",
                "marketCountry": "KR",
                "currency": "KRW",
                "quantity": "10",
                "lastPrice": "1",
                "averagePurchasePrice": "1",
            },
            {
                "symbol": "AAPL",
                "name": "Apple",
                "marketCountry": "US",
                "currency": "USD",
                "quantity": "2",
                "lastPrice": "1",
                "averagePurchasePrice": "1",
            },
        ]
    )
    assert [h["ticker"] for h in grouped["KRW"]] == ["005930"]
    assert [h["ticker"] for h in grouped["USD"]] == ["AAPL"]


def test_ip_block_message():
    msg = humanize_toss_error(403, {"error": {"code": "edge-blocked", "message": "blocked"}})
    assert "허용 IP" in msg
    assert "403" in msg or "막았" in msg
