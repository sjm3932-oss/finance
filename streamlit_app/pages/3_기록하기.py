"""기록하기 — OCR 업로드 + 수기 입력 (승인는 별도 메뉴)."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.asset_flows_ui import render_flow_forms  # noqa: E402
from lib.auth import ensure_profile, require_auth  # noqa: E402
from lib.debt_ui import render_debt_forms  # noqa: E402
from lib.record_ui import render_ocr_upload  # noqa: E402
from lib.tax_ui import render_tax_forms  # noqa: E402
from lib.theme import apply_theme, page_hero, render_subnav  # noqa: E402

apply_theme(max_width=1120)

VIEWS = ["OCR", "수기"]


def main() -> None:
    page_hero(
        "기록하기",
        "스크린샷 OCR 업로드와 수기 입력. 승인은 「승인하기」메뉴에서 합니다.",
        compact=True,
    )
    view = render_subnav(VIEWS, state_key="record_view", default="OCR")

    user, client = require_auth()
    ensure_profile(user, client)

    if view == "OCR":
        st.caption("잔고 · 매매 · 배당 · 부채 스크린샷 → 파싱 → 스테이징")
        render_ocr_upload(client, user)
        st.info("업로드 후 사이드바 **승인하기**에서 표로 검토·승인하세요.")
    else:
        st.caption("매매 · 배당 · 현금 · 부채 · 세금 수기 입력")
        tabs = st.tabs(["매매·배당·현금", "부채", "세금"])
        with tabs[0]:
            render_flow_forms(client, user)
        with tabs[1]:
            render_debt_forms(client, user)
        with tabs[2]:
            render_tax_forms(client, user)


main()
