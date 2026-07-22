"""Shared chart period selection (no drag-zoom — buttons only)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

PERIOD_OPTIONS: list[tuple[str, int | None]] = [
    ("3개월", 3),
    ("6개월", 6),
    ("1년", 12),
    ("3년", 36),
    ("전체", None),
]


def period_radio(
    *,
    key: str,
    default: str = "1년",
    label: str = "기간",
) -> int | None:
    """Render horizontal period buttons; return months-back (None = 전체)."""
    labels = [p[0] for p in PERIOD_OPTIONS]
    default_idx = labels.index(default) if default in labels else 0
    choice = st.radio(
        label,
        options=labels,
        index=default_idx,
        horizontal=True,
        key=key,
        help="차트 드래그 대신 기간 버튼으로 조회하세요.",
    )
    return dict(PERIOD_OPTIONS)[choice]


def filter_by_period(
    df: pd.DataFrame,
    months: int | None,
    *,
    date_col: str = "event_date",
) -> pd.DataFrame:
    """Keep rows within the last N months of the latest date in ``date_col``."""
    if df is None or df.empty or months is None:
        return df if df is not None else pd.DataFrame()
    if date_col not in df.columns:
        return df
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    tmp = out.dropna(subset=[date_col])
    if tmp.empty:
        return out.iloc[0:0].copy()
    latest = tmp[date_col].max()
    end_month = latest.to_period("M").to_timestamp()
    start = end_month - pd.DateOffset(months=months - 1)
    return out[out[date_col] >= start].copy()
