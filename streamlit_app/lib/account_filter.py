"""Shared brokerage-account filter for 내 자산 tabs."""

from __future__ import annotations

import streamlit as st


def account_map(client) -> dict[str, str]:
    rows = client.table("accounts").select("id,institution").execute().data or []
    return {str(a["id"]): (a.get("institution") or "계좌") for a in rows}


def account_options(client) -> list[str]:
    names = sorted({n for n in account_map(client).values() if n})
    return ["전체"] + names


def account_ids_for_label(client, label: str) -> list[str] | None:
    """None = 전체 (no filter). Otherwise list of account UUIDs."""
    if not label or label == "전체":
        return None
    amap = account_map(client)
    ids = [aid for aid, name in amap.items() if name == label]
    return ids


def render_account_selector(client, *, key: str = "dash_account_filter") -> str:
    options = account_options(client)
    current = st.session_state.get(key)
    if current not in options:
        st.session_state[key] = "전체"
    return st.selectbox(
        "계좌",
        options,
        key=key,
        help="선택한 증권사 계좌의 데이터만 표시합니다.",
    )


def filter_df_by_account_ids(df, account_ids: list[str] | None, col: str = "account_id"):
    """Filter a DataFrame by account_id column. None ids → no filter."""
    if account_ids is None or df is None or getattr(df, "empty", True):
        return df
    if col not in df.columns:
        return df.iloc[0:0].copy()
    ids = {str(a) for a in account_ids}
    return df[df[col].astype(str).isin(ids)].copy()
