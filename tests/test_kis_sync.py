"""Tests for KIS holdings / fill / dividend mapping (no live API)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from kis_client import (  # noqa: E402
    date_windows,
    domestic_cash,
    holdings_by_currency,
    humanize_kis_error,
    is_rate_limited,
    is_trust_account_only,
    map_domestic_dividend,
    map_domestic_fill,
    map_domestic_holding,
    map_overseas_dividend,
    map_overseas_fill,
    map_overseas_holding,
    merge_holdings,
    merge_credentials,
    normalize_kr_ticker,
    overseas_cash,
    parse_account_spec,
    parse_accounts,
)


def test_parse_account_specs():
    assert parse_account_spec("12345678-01") == ("12345678", "01")
    assert parse_account_spec("1234567801") == ("12345678", "01")
    assert parse_account_spec("12345678") == ("12345678", "01")
    assert parse_accounts("12345678", "01", "12345678-22") == [
        ("12345678", "01"),
        ("12345678", "22"),
    ]
    assert parse_accounts("12345678", "01", "12345678-01") == [("12345678", "01")]
    assert parse_accounts("", "01", "64209634-01,64209634-21,64209634-22,64209634-29") == [
        ("64209634", "01"),
        ("64209634", "21"),
        ("64209634", "22"),
        ("64209634", "29"),
    ]
    assert parse_account_spec("21") is None


def test_normalize_kr_ticker():
    assert normalize_kr_ticker("A005930") == "005930"
    assert normalize_kr_ticker("5930") == "005930"
    assert normalize_kr_ticker("005930.KS") == "005930"


def test_map_domestic_holding():
    row = map_domestic_holding(
        {
            "pdno": "A005930",
            "prdt_name": "삼성전자",
            "hldg_qty": "10",
            "pchs_avg_pric": "65000",
            "prpr": "72000",
        }
    )
    assert row == {
        "ticker": "005930",
        "name": "삼성전자",
        "quantity": 10.0,
        "avg_price": 65000.0,
        "currency": "KRW",
        "last_price": 72000.0,
    }
    assert map_domestic_holding({"pdno": "005930", "hldg_qty": "0"}) is None


def test_map_overseas_holding():
    row = map_overseas_holding(
        {
            "ovrs_pdno": "AAPL",
            "ovrs_item_name": "Apple",
            "ovrs_cblc_qty": "1.5",
            "pchs_avg_pric": "185",
            "now_pric2": "210.1",
            "tr_crcy_cd": "USD",
        }
    )
    assert row["ticker"] == "AAPL"
    assert row["quantity"] == 1.5
    assert row["currency"] == "USD"


def test_merge_same_ticker_across_accounts():
    merged = merge_holdings(
        [
            {
                "ticker": "005930",
                "name": "삼성전자",
                "quantity": 10,
                "avg_price": 70000,
                "currency": "KRW",
                "last_price": 72000,
            },
            {
                "ticker": "005930",
                "name": "삼성전자",
                "quantity": 10,
                "avg_price": 60000,
                "currency": "KRW",
                "last_price": 73000,
            },
        ]
    )
    assert len(merged) == 1
    assert merged[0]["quantity"] == 20
    assert merged[0]["avg_price"] == 65000
    grouped = holdings_by_currency(merged)
    assert [h["ticker"] for h in grouped["KRW"]] == ["005930"]


def test_domestic_cash():
    assert domestic_cash({"dnca_tot_amt": "123456"}) == 123456.0


def test_overseas_cash_usd_row():
    assert (
        overseas_cash(
            [
                {"crcy_cd": "KRW", "dncl_amt": "1"},
                {"crcy_cd": "USD", "frcr_dncl_amt_2": "88.5"},
            ]
        )
        == 88.5
    )


def test_map_domestic_fill():
    row = map_domestic_fill(
        {
            "odno": "0000123456",
            "pdno": "005930",
            "sll_buy_dvsn_cd": "02",
            "tot_ccld_qty": "10",
            "avg_prvs": "70000",
            "ord_dt": "20260328",
            "tot_tr_cost": "1400",
        },
        cano="12345678",
    )
    assert row == {
        "external_id": "kis:kr:12345678:2026-03-28:0000123456",
        "ticker": "005930",
        "trade_type": "buy",
        "price": 70000.0,
        "quantity": 10.0,
        "fee": 1400.0,
        "currency": "KRW",
        "trade_date": "2026-03-28",
        "reason": "한투 체결",
    }
    assert (
        map_domestic_fill(
            {"odno": "1", "pdno": "005930", "sll_buy_dvsn_cd": "02", "tot_ccld_qty": "0"},
            cano="1",
        )
        is None
    )


def test_map_overseas_fill_sell():
    row = map_overseas_fill(
        {
            "odno": "US-99",
            "pdno": "AAPL",
            "sll_buy_dvsn_cd": "01",
            "ft_ccld_qty": "2",
            "ft_ccld_unpr3": "185.25",
            "ord_dt": "2026-03-29",
            "tr_cmsn": "0.66",
            "tr_crcy_cd": "USD",
        },
        cano="12345678",
    )
    assert row is not None
    assert row["trade_type"] == "sell"
    assert row["ticker"] == "AAPL"
    assert row["quantity"] == 2.0
    assert row["price"] == 185.25
    assert abs(row["fee"] - 0.66) < 1e-9
    assert row["trade_date"] == "2026-03-29"


def test_map_domestic_dividend():
    row = map_domestic_dividend(
        {
            "pdno": "005930",
            "prdt_name": "삼성전자",
            "rght_type_cd": "03",
            "rght_type_name": "현금배당",
            "last_alct_amt": "15400",
            "tax_amt": "2310",
            "pay_dt": "20260415",
        },
        cano="12345678",
    )
    assert row is not None
    assert row["ticker"] == "005930"
    assert row["amount"] == 13090.0
    assert row["pay_date"] == "2026-04-15"
    assert row["currency"] == "KRW"
    assert map_domestic_dividend(
        {"pdno": "005930", "rght_type_name": "유상증자", "last_alct_amt": "1", "pay_dt": "20260415"},
        cano="1",
    ) is None


def test_map_overseas_dividend_by_name():
    row = map_overseas_dividend(
        {
            "pdno": "SCHD",
            "prdt_name": "Schwab US Dividend Equity ETF",
            "sll_buy_dvsn_name": "배당금입금",
            "tr_amt": "12.4",
            "trad_dt": "20260328",
            "tr_crcy_cd": "USD",
        },
        cano="12345678",
    )
    assert row is not None
    assert row["ticker"] == "SCHD"
    assert row["amount"] == 12.4
    assert row["currency"] == "USD"
    assert (
        map_overseas_dividend(
            {
                "pdno": "AAPL",
                "sll_buy_dvsn_name": "매수",
                "tr_amt": "100",
                "trad_dt": "20260328",
            },
            cano="1",
        )
        is None
    )


def test_date_windows():
    windows = date_windows(date(2026, 1, 1), date(2026, 2, 10), 30)
    assert windows[0] == (date(2026, 1, 1), date(2026, 1, 30))
    assert windows[-1][1] == date(2026, 2, 10)


def test_product_memo_and_code():
    from kis_client import memo_product_code, product_label, product_memo

    assert product_label("01") == "01 위탁"
    assert product_label("21") == "21 ISA"
    assert product_memo("29") == "29 퇴직연금"
    assert memo_product_code("01 위탁") == "01"
    assert memo_product_code("21 ISA") == "21"
    assert memo_product_code("01·21·22·29 합산") is None
    assert memo_product_code("") is None
    assert memo_product_code(None) is None
    rate = humanize_kis_error(500, {"msg_cd": "EGW00201", "msg1": "초당 거래건수를 초과하였습니다."})
    assert "한도" in rate
    ip = humanize_kis_error(403, {"msg_cd": "EGW00204", "msg1": "blocked"})
    assert "IP" in ip
    auth = humanize_kis_error(401, {"msg_cd": "EGW00121"})
    assert "앱키" in auth
    assert is_rate_limited(429, {})
    assert is_rate_limited(200, {"msg_cd": "EGW00201"})
    assert not is_rate_limited(403, {"msg_cd": "EGW00204"})
    assert is_trust_account_only({"msg_cd": "APAC0489", "msg1": "위탁계좌인 경우만 사용가능합니다"})


def test_merge_credentials_prefers_env():
    key, secret, env, accounts = merge_credentials(
        env_key="e-key",
        env_secret="e-sec",
        env_env="real",
        env_cano="",
        env_product="01",
        env_accounts="12345678-01",
        db={
            "app_key": "d-key",
            "app_secret": "d-sec",
            "accounts": "99999999-01",
            "env": "demo",
        },
    )
    assert key == "e-key"
    assert secret == "e-sec"
    assert env == "real"
    assert accounts == [("12345678", "01")]


def test_merge_credentials_falls_back_to_db():
    key, secret, env, accounts = merge_credentials(
        env_key="",
        env_secret="",
        env_env="",
        env_cano="",
        env_product="01",
        env_accounts="",
        db={
            "app_key": "d-key",
            "app_secret": "d-sec",
            "accounts": "64209634-01,64209634-21",
            "env": "real",
        },
    )
    assert key == "d-key"
    assert secret == "d-sec"
    assert env == "real"
    assert accounts == [("64209634", "01"), ("64209634", "21")]
