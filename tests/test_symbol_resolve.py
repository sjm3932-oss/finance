"""Tests for OCR ticker ↔ name enrichment."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "streamlit_app"))

from lib.symbol_resolve import (  # noqa: E402
    _norm_ticker,
    enrich_parsed_symbols,
    enrich_symbol_row,
)


def test_norm_ticker_strips_kr_suffix():
    assert _norm_ticker("005930.KS") == "005930"
    assert _norm_ticker("005930.kq") == "005930"
    assert _norm_ticker("QQQM") == "QQQM"


def test_enrich_fills_name_from_ticker_via_holdings():
    row = enrich_symbol_row(
        {"ticker": "005930", "quantity": 10},
        by_ticker={"005930": "삼성전자"},
        by_name={},
        cache={},
    )
    assert row["ticker"] == "005930"
    assert row["name"] == "삼성전자"


def test_enrich_fills_ticker_from_name_via_holdings():
    row = enrich_symbol_row(
        {"name": "삼성전자", "quantity": 10},
        by_ticker={},
        by_name={"삼성전자": "005930"},
        cache={},
    )
    assert row["ticker"] == "005930"
    assert row["name"] == "삼성전자"


def test_enrich_parsed_symbols_all_sections():
    client = MagicMock()
    client.table.return_value.select.return_value.execute.return_value.data = [
        {"ticker": "QQQM", "name": "Invesco NASDAQ 100 ETF"},
    ]
    parsed = {
        "trades": [{"ticker": "QQQM", "price": 1}],
        "dividends": [{"name": "Invesco NASDAQ 100 ETF", "amount": 1}],
        "holdings_snapshot": [{"ticker": "QQQM", "quantity": 2}],
        "debts": [],
    }
    out = enrich_parsed_symbols(parsed, client)
    assert out["trades"][0]["name"] == "Invesco NASDAQ 100 ETF"
    assert out["dividends"][0]["ticker"] == "QQQM"
    assert out["holdings_snapshot"][0]["name"] == "Invesco NASDAQ 100 ETF"


@patch("lib.symbol_resolve._naver_name", return_value="삼성전자")
def test_enrich_name_from_naver(_mock_naver):
    row = enrich_symbol_row(
        {"ticker": "005930"},
        by_ticker={},
        by_name={},
        cache={},
    )
    assert row["name"] == "삼성전자"


@patch("lib.symbol_resolve._naver_ticker", return_value="005930")
def test_enrich_ticker_from_naver(_mock_naver):
    row = enrich_symbol_row(
        {"name": "삼성전자"},
        by_ticker={},
        by_name={},
        cache={},
    )
    assert row["ticker"] == "005930"
