"""Tax views: dashboard = read-only; 기록하기 수기 = write forms."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from lib.ui_ko import rename_columns


def render_tax_dashboard(client) -> None:
    """Read-only tax estimate for the dashboard."""
    st.caption(
        "해외주식 양도소득세 추정(기본공제 250만원 · 22%). "
        "숫자 입력/수정은 「기록하기 → 수기」에서만 합니다."
    )
    year = st.number_input(
        "세무연도",
        min_value=2020,
        max_value=2100,
        value=date.today().year,
        step=1,
        key="dash_tax_year_ro",
    )
    calc = (
        client.table("v_tax_calculation")
        .select("*")
        .eq("tax_year", int(year))
        .execute()
        .data
        or []
    )
    if not calc:
        st.info("해당 연도 기록이 없습니다. 「기록하기 → 수기 → 세금」에서 입력하세요.")
        return

    for r in calc:
        taxable = float(r.get("taxable_gain") or 0)
        estimated = float(r.get("estimated_tax") or 0)
        c1, c2 = st.columns(2)
        c1.metric("과세대상 양도차익", f"₩{taxable:,.0f}")
        c2.metric("예상 세금 (22%)", f"₩{estimated:,.0f}")

    st.dataframe(rename_columns(pd.DataFrame(calc)), use_container_width=True, hide_index=True)
    st.caption("공식: max(누적양도차익 − 기본공제, 0) × 0.22")


def render_tax_forms(client, user) -> None:
    """Write path for tax records — 기록하기 → 수기 only."""
    st.caption("누적 양도차익·기본공제·배당세를 입력하면 예상 세금이 계산됩니다.")
    year = st.number_input(
        "세무연도",
        min_value=2020,
        max_value=2100,
        value=date.today().year,
        step=1,
        key="record_tax_year",
    )
    records = (
        client.table("tax_records")
        .select("*")
        .eq("tax_year", int(year))
        .execute()
        .data
        or []
    )
    existing = records[0] if records else {}
    with st.form("record_tax_form"):
        cum = st.number_input(
            "누적 양도차익 (원)",
            min_value=0.0,
            value=float(existing.get("cum_capital_gain") or 0),
            step=10000.0,
            format="%.0f",
        )
        threshold = st.number_input(
            "기본공제 (원)",
            min_value=0.0,
            value=float(existing.get("tax_threshold") or 2_500_000),
            step=10000.0,
            format="%.0f",
        )
        dividend_tax = st.number_input(
            "배당세 (원)",
            min_value=0.0,
            value=float(existing.get("dividend_tax") or 0),
            step=1000.0,
            format="%.0f",
        )
        if st.form_submit_button("저장", type="primary"):
            client.table("tax_records").upsert(
                {
                    "user_id": str(user.id),
                    "tax_year": int(year),
                    "cum_capital_gain": cum,
                    "tax_threshold": threshold,
                    "dividend_tax": dividend_tax,
                },
                on_conflict="user_id,tax_year",
            ).execute()
            st.success("저장됨")
            st.rerun()

    calc = (
        client.table("v_tax_calculation")
        .select("*")
        .eq("tax_year", int(year))
        .execute()
        .data
        or []
    )
    if calc:
        r = calc[0]
        c1, c2 = st.columns(2)
        c1.metric("과세대상 양도차익", f"₩{float(r.get('taxable_gain') or 0):,.0f}")
        c2.metric("예상 세금 (22%)", f"₩{float(r.get('estimated_tax') or 0):,.0f}")


def render_tax_panel(client, user=None) -> None:
    render_tax_dashboard(client)
