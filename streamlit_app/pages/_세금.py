"""Hidden page — tax lives under 대시보드 → 세금."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth import ensure_profile, require_auth  # noqa: E402
from lib.tax_ui import render_tax_dashboard  # noqa: E402
from lib.theme import apply_theme, page_hero, render_bottom_actions  # noqa: E402

st.set_page_config(page_title="세금 · 부자뚱", page_icon="💚", layout="wide")
apply_theme(max_width=1120)


def main() -> None:
    page_hero(
        "세금",
        "해외주식 양도소득세 추정(조회). 입력은 기록하기에서 하세요.",
    )
    user, client = require_auth()
    ensure_profile(user, client)
    render_tax_dashboard(client)
    render_bottom_actions(enabled=True)


main()
