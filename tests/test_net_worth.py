"""Tests for net worth composition and allocation drift."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "streamlit_app"))

from lib.net_worth import (  # noqa: E402
    allocation_actual,
    allocation_drift,
    compute_net_worth,
)


def test_compute_net_worth_basic():
    accounts = [
        {
            "id": "a1",
            "account_type": "brokerage",
            "currency": "KRW",
            "ownership": "joint",
            "cash_balance": 1_000_000,
        },
        {
            "id": "a2",
            "account_type": "bank",
            "currency": "KRW",
            "ownership": "mine",
            "cash_balance": 500_000,
        },
    ]
    live = [
        {
            "account_id": "a1",
            "ticker": "005930",
            "ccy": "KRW",
            "value": 10_000_000,
        },
        {
            "account_id": "a1",
            "ticker": "AAPL",
            "ccy": "USD",
            "value": 1000,
        },
    ]
    other = [
        {"name": "아파트", "value_krw": 50_000_000, "ownership": "joint"},
        {"name": "IRP", "value_krw": 2_000_000, "ownership": "mine"},
    ]
    nw = compute_net_worth(
        live,
        accounts=accounts,
        other_assets=other,
        total_debt=20_000_000,
        usdkrw=1000.0,
    )
    # invest: 10M KRW + 1000*1000 USD = 11M
    assert nw["invest"] == 11_000_000
    # cash: 1M + 0.5M = 1.5M
    assert nw["cash"] == 1_500_000
    assert nw["other"] == 52_000_000
    assert nw["debt"] == 20_000_000
    assert nw["net"] == 11_000_000 + 1_500_000 + 52_000_000 - 20_000_000
    assert nw["domestic"] == 10_000_000
    assert nw["overseas"] == 1_000_000


def test_ownership_filter_excludes():
    accounts = [
        {
            "id": "a1",
            "account_type": "brokerage",
            "currency": "KRW",
            "ownership": "joint",
            "cash_balance": 0,
        }
    ]
    live = [{"account_id": "a1", "ticker": "005930", "ccy": "KRW", "value": 5_000_000}]
    other = [{"name": "X", "value_krw": 1_000_000, "ownership": "spouse"}]
    nw = compute_net_worth(
        live,
        accounts=accounts,
        other_assets=other,
        total_debt=0,
        usdkrw=None,
        ownership="joint",
    )
    assert nw["invest"] == 5_000_000
    assert nw["other"] == 0  # spouse ownership excluded


def test_allocation_drift():
    nw = {
        "gross": 100.0,
        "domestic": 50.0,
        "overseas": 30.0,
        "cash": 15.0,
        "other": 5.0,
    }
    actual = allocation_actual(nw)
    assert round(actual["domestic"], 1) == 50.0
    rows = allocation_drift(actual, {"domestic": 40, "overseas": 40, "cash": 15, "other": 5})
    by = {r["category"]: r for r in rows}
    assert by["domestic"]["drift_pct"] == 10.0
    assert by["overseas"]["drift_pct"] == -10.0
