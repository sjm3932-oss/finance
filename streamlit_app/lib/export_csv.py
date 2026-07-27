"""CSV download helpers for dashboard tables."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st


def download_csv_button(
    df: pd.DataFrame,
    *,
    filename_prefix: str,
    label: str = "CSV 다운로드",
    key: str,
) -> None:
    if df is None or df.empty:
        return
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label,
        data=csv,
        file_name=f"{filename_prefix}_{date.today().isoformat()}.csv",
        mime="text/csv",
        key=key,
        use_container_width=True,
    )
