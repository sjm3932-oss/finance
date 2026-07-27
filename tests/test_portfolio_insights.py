"""Unit tests for portfolio insight helpers (no DB)."""

from __future__ import annotations

import pandas as pd

from lib.portfolio_insights import (
    allocation_frames,
    allocation_leaves,
    dividend_stats,
    market_region,
)
from lib.theme import chart_layout


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
            "return_%": 10.0,
        },
        {
            "ticker": "AAPL",
            "name": "Apple",
            "value": 100,
            "ccy": "USD",
            "institution": "토스",
            "return_%": -5.0,
        },
        {
            "ticker": "005930",
            "name": "삼성전자",
            "value": 500000,
            "ccy": "KRW",
            "institution": "토스",
            "return_%": 10.0,
        },
    ]
    by_t, by_r, by_a = allocation_frames(rows, usdkrw=1000.0)
    assert abs(by_t[by_t["ticker"] == "005930"]["value_krw"].sum() - 1_500_000) < 1
    assert abs(by_t[by_t["ticker"] == "AAPL"]["value_krw"].sum() - 100_000) < 1
    assert set(by_r["label"]) == {"국내", "해외"}
    assert set(by_a["label"]) == {"키움", "토스"}

    leaves = allocation_leaves(rows, usdkrw=1000.0)
    assert len(leaves) == 3
    assert "return_pct" in leaves.columns


def test_treemap_layout_no_kwarg_collision():
    """Regression: never unpack chart_layout alongside title=/legend= kwargs."""
    import plotly.express as px

    df = pd.DataFrame(
        {
            "root": ["전체", "전체"],
            "label": ["삼성전자", "Apple"],
            "value_krw": [1_500_000, 100_000],
            "return_pct": [10.0, -5.0],
            "ret_label": ["+10.0%", "-5.0%"],
            "ticker": ["005930", "AAPL"],
        }
    )
    fig = px.treemap(
        df,
        path=["root", "label"],
        values="value_krw",
        color="return_pct",
        color_continuous_midpoint=0,
        custom_data=["ret_label", "ticker", "value_krw"],
    )
    layout = chart_layout(
        400,
        title="종목 비중",
        margin=dict(l=4, r=4, t=48, b=8),
    )
    fig.update_layout(layout)  # must not raise TypeError


def test_dividend_stats_empty():
    stats = dividend_stats(pd.DataFrame(), None)
    assert stats["month_krw"] == 0.0
    assert stats["expected_krw"] == 0.0
