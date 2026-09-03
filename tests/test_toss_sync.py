"""Tests for Toss holdings mapping (no live API)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from toss_client import (  # noqa: E402
    date_windows,
    extract_holdings_items,
    extract_orders,
    holdings_by_currency,
    humanize_toss_error,
    kst_auto_sync_due,
    map_filled_order,
    map_holding,
    normalize_ticker,
    pagination_cursor,
    parse_auto_sync_hours,
    parse_yahoo_dividends,
    yahoo_chart_symbol,
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


def test_map_filled_market_uses_amount_over_qty():
    row = map_filled_order(
        {
            "orderId": "ord-mkt",
            "symbol": "AAPL",
            "side": "BUY",
            "orderType": "MARKET",
            "status": "FILLED",
            "currency": "USD",
            "price": None,
            "orderedAt": "2026-03-10T22:31:00+09:00",
            "execution": {
                "filledQuantity": "2",
                "averageFilledPrice": None,
                "filledAmount": "370.5",
                "commission": "0.1",
                "tax": "0",
                "filledAt": "2026-03-10T22:31:05+09:00",
            },
        }
    )
    assert row is not None
    assert row["quantity"] == 2.0
    assert abs(row["price"] - 185.25) < 1e-9
    assert row["trade_date"] == "2026-03-10"


def test_map_filled_flat_fields_and_nested_stock():
    row = map_filled_order(
        {
            "id": "ord-flat",
            "side": "BUY",
            "currency": "KRW",
            "stock": {"stockCode": "005930"},
            "filledQuantity": "10",
            "filledAmount": "700000",
            "orderedAt": "2026-03-10T09:01:00+09:00",
        }
    )
    assert row is not None
    assert row["external_id"] == "ord-flat"
    assert row["ticker"] == "005930"
    assert row["quantity"] == 10.0
    assert row["price"] == 70000.0


def test_extract_orders_and_cursor():
    nested = {"result": {"orders": [{"orderId": "a"}], "nextCursor": "tok-1", "hasNext": True}}
    assert extract_orders(nested) == [{"orderId": "a"}]
    assert pagination_cursor(nested) == (True, "tok-1")

    wrapped = {"result": {"data": {"items": [{"orderId": "b"}]}}}
    assert extract_orders(wrapped) == [{"orderId": "b"}]
    assert extract_holdings_items({"result": {"items": [{"symbol": "AAPL"}]}}) == [{"symbol": "AAPL"}]


def test_closed_order_date_windows_split_long_lookbacks():
    windows = date_windows("2026-01-01", "2026-09-01", 90)
    assert windows[0] == ("2026-01-01", "2026-03-31")
    assert windows[-1][1] == "2026-09-01"
    assert all(
        (int(end.replace("-", "")) - int(start.replace("-", ""))) >= 0 for start, end in windows
    )


def test_parse_yahoo_dividends_scales_by_holding_quantity():
    payload = {
        "chart": {
            "result": [
                {
                    "events": {
                        "dividends": {
                            "1719792000": {"date": 1719792000, "amount": 0.7},
                        }
                    }
                }
            ]
        }
    }
    rows = parse_yahoo_dividends(
        payload,
        ticker="SCHD",
        quantity=100,
        start="2024-01-01",
        end="2026-09-01",
    )
    assert len(rows) == 1
    assert abs(rows[0]["amount"] - 70) < 1e-9
    assert rows[0]["ticker"] == "SCHD"
    assert rows[0]["pay_date"] == "2024-07-01"
    assert rows[0]["external_id"].startswith("toss:div:SCHD:2024-07-01:")
    assert yahoo_chart_symbol("005930") == ["005930.KS", "005930.KQ"]
    assert yahoo_chart_symbol("SCHD") == ["SCHD"]
    kis_rows = parse_yahoo_dividends(
        payload,
        ticker="458730",
        quantity=10,
        start="2024-01-01",
        end="2026-09-01",
        source="kis",
    )
    assert kis_rows[0]["external_id"].startswith("kis:div:est:458730:2024-07-01:")
    assert kis_rows[0]["memo"] == "한투 배당(추정)"
    assert kis_rows[0]["currency"] == "KRW"


def test_closed_not_supported_message():
    msg = humanize_toss_error(400, {"error": {"code": "closed-not-supported", "message": "nope"}})
    assert "CLOSED" in msg
    assert "배당" in msg

