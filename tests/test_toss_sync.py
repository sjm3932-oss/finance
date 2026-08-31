"""Tests for Toss holdings mapping (no live API)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from toss_client import (  # noqa: E402
    holdings_by_currency,
    humanize_toss_error,
    kst_auto_sync_due,
    map_filled_order,
    map_holding,
    normalize_ticker,
    parse_auto_sync_hours,
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


FILLED_KR = {
    "orderId": "ord-samsung",
    "symbol": "005930",
    "side": "BUY",
    "orderType": "LIMIT",
    "status": "FILLED",
    "currency": "KRW",
    "orderedAt": "2026-03-28T09:30:00+09:00",
    "execution": {
        "filledQuantity": "10",
        "averageFilledPrice": "70000",
        "filledAmount": "700000",
        "commission": "1400",
        "tax": "0",
        "filledAt": "2026-03-28T09:31:15+09:00",
    },
}

PENDING = {
    "orderId": "ord-pending",
    "symbol": "005930",
    "side": "BUY",
    "status": "PENDING",
    "currency": "KRW",
    "orderedAt": "2026-03-29T09:30:00+09:00",
    "execution": {
        "filledQuantity": "0",
        "averageFilledPrice": None,
        "commission": None,
        "tax": None,
        "filledAt": None,
    },
}

PARTIAL_CANCEL = {
    "orderId": "ord-aapl-partial",
    "symbol": "AAPL",
    "side": "SELL",
    "status": "CANCELED",
    "currency": "USD",
    "orderedAt": "2026-03-29T10:00:00+09:00",
    "execution": {
        "filledQuantity": "2",
        "averageFilledPrice": "185.25",
        "commission": "0.66",
        "tax": "0",
        "filledAt": "2026-03-29T10:00:05+09:00",
    },
}


def test_map_filled_buy():
    row = map_filled_order(FILLED_KR)
    assert row == {
        "external_id": "ord-samsung",
        "ticker": "005930",
        "trade_type": "buy",
        "price": 70000.0,
        "quantity": 10.0,
        "fee": 1400.0,
        "currency": "KRW",
        "trade_date": "2026-03-28",
        "reason": "토스 체결",
    }


def test_skip_unfilled():
    assert map_filled_order(PENDING) is None


def test_map_partial_sell_uses_fill():
    row = map_filled_order(PARTIAL_CANCEL)
    assert row is not None
    assert row["trade_type"] == "sell"
    assert row["ticker"] == "AAPL"
    assert row["quantity"] == 2.0
    assert row["price"] == 185.25
    assert abs(row["fee"] - 0.66) < 1e-9
    assert row["trade_date"] == "2026-03-29"
    assert row["currency"] == "USD"


def test_parse_auto_sync_hours():
    assert parse_auto_sync_hours(None) == [6, 16]
    assert parse_auto_sync_hours("") == [6, 16]
    assert parse_auto_sync_hours("6,16") == [6, 16]
    assert parse_auto_sync_hours("16, 6, 6") == [6, 16]
    assert parse_auto_sync_hours("25, -1, abc") == [6, 16]


def test_kst_slots_six_and_sixteen():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    kst = ZoneInfo("Asia/Seoul")
    hours = [6, 16]
    d = datetime(2026, 8, 31, tzinfo=kst)
    assert kst_auto_sync_due(d.replace(hour=5, minute=59), None, hours) is False
    assert kst_auto_sync_due(d.replace(hour=6, minute=0), None, hours) is True
    synced_six = d.replace(hour=6, minute=5)
    assert kst_auto_sync_due(d.replace(hour=10, minute=0), synced_six, hours) is False
    assert kst_auto_sync_due(d.replace(hour=16, minute=0), synced_six, hours) is True
    synced_sixteen = d.replace(hour=16, minute=5)
    assert kst_auto_sync_due(d.replace(hour=16, minute=30), synced_sixteen, hours) is False
    yesterday = datetime(2026, 8, 30, 16, 5, tzinfo=kst)
    assert kst_auto_sync_due(d.replace(hour=10, minute=0), yesterday, hours) is True
    # last_ok from Postgres is UTC; 21:05 UTC = 06:05 KST
    from datetime import timezone

    last_utc = datetime(2026, 8, 30, 21, 5, tzinfo=timezone.utc)
    assert kst_auto_sync_due(d.replace(hour=10, minute=0), last_utc, hours) is False
    assert kst_auto_sync_due(d.replace(hour=16, minute=0), last_utc, hours) is True

