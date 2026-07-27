"""Tests for KR/US price routing (Naver vs Yahoo)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "streamlit_app"))

from lib.market_data import (  # noqa: E402
    fetch_price,
    is_korean_ticker,
    normalize_ticker,
    refresh_tickers,
)


class TickerRoutingTests(unittest.TestCase):
    def test_normalize_strips_ks(self):
        self.assertEqual(normalize_ticker("005930.KS"), "005930")
        self.assertEqual(normalize_ticker("qqqm"), "QQQM")

    def test_is_korean(self):
        self.assertTrue(is_korean_ticker("005930"))
        self.assertTrue(is_korean_ticker("005930.KQ"))
        self.assertFalse(is_korean_ticker("QQQM"))
        self.assertFalse(is_korean_ticker("AAPL"))

    @patch("lib.market_data.fetch_naver_price")
    @patch("lib.market_data.fetch_yahoo_price")
    def test_fetch_price_routes_kr_to_naver(self, yahoo, naver):
        naver.return_value = {
            "ticker": "005930",
            "price": 1.0,
            "currency": "KRW",
            "updated_at": "x",
        }
        fetch_price("005930")
        naver.assert_called_once()
        yahoo.assert_not_called()

    @patch("lib.market_data.fetch_naver_price")
    @patch("lib.market_data.fetch_yahoo_price")
    def test_fetch_price_routes_us_to_yahoo(self, yahoo, naver):
        yahoo.return_value = {
            "ticker": "QQQM",
            "price": 1.0,
            "currency": "USD",
            "updated_at": "x",
        }
        fetch_price("QQQM")
        yahoo.assert_called_once()
        naver.assert_not_called()

    @patch("lib.market_data.fetch_price")
    def test_refresh_tickers_dedupes(self, fetch):
        fetch.side_effect = lambda t: {
            "ticker": t,
            "price": 1.0,
            "currency": "USD" if t == "QQQM" else "KRW",
            "updated_at": "x",
        }
        rows, errors = refresh_tickers(["QQQM", "qqqm", "005930"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
