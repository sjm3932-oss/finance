"""Page: Overseas capital-gains tax estimate (v_tax_calculation)."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth import ensure_profile, require_auth  # noqa: E402
from lib.ui_ko import rename_columns  # noqa: E402
from lib.theme import apply_theme, page_hero  # noqa: E402


st.set_page_config(page_title="세금", page_icon="💚", layout="wide")
apply_theme(max_width=1120)


def main() -> None:
    page_hero("세금", "해외주식 양도소득세 추정 — 기본공제 250만원 · 세율 22%")
    st.caption("해외주식 양도소득세 추정 — 기본공제 250만원 · 세율 22%")

    user, client = require_auth()
    ensure_profile(user, client)

    year = st.number_input("세무연도", min_value=2020, max_value=2100, value=date.today().year, step=1)

    records = (
        client.table("tax_records")
        .select("*")
        .eq("tax_year", int(year))
        .execute()
        .data
        or []
    )

    with st.expander("세금 기록 입력/수정", expanded=not records):
        existing = records[0] if records else {}
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
        if st.button("저장", type="primary"):
            payload = {
                "user_id": str(user.id),
                "tax_year": int(year),
                "cum_capital_gain": cum,
                "tax_threshold": threshold,
                "dividend_tax": dividend_tax,
            }
            client.table("tax_records").upsert(payload, on_conflict="user_id,tax_year").execute()
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

    if not calc:
        st.info("해당 연도 기록이 없습니다. 위에서 누적 양도차익을 저장하세요.")
        return

    # Prefer couple-total if multiple users; for now show all
    for r in calc:
        taxable = float(r.get("taxable_gain") or 0)
        estimated = float(r.get("estimated_tax") or 0)
        st.subheader(f"사용자 `{r.get('user_id', '')[:8]}…`")
        c1, c2 = st.columns(2)
        c1.metric("과세대상 양도차익", f"₩{taxable:,.0f}")
        c2.metric("예상 세금 (22%)", f"₩{estimated:,.0f}")

    st.dataframe(rename_columns(pd.DataFrame(calc)), use_container_width=True, hide_index=True)
    st.caption("공식: max(누적양도차익 − 기본공제, 0) × 0.22")


main()
