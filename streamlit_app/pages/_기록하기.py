"""Page: Unified write path — OCR → review → manual entry."""

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
from lib.record_ui import render_ocr_upload, render_staging_review  # noqa: E402
from lib.tax_ui import render_tax_forms  # noqa: E402
from lib.theme import apply_theme, page_hero, render_bottom_actions, render_subnav  # noqa: E402

st.set_page_config(page_title="기록하기 · 부자뚱", page_icon="💚", layout="wide")
apply_theme(max_width=1120)

VIEWS = ["OCR", "검토", "수기"]


def main() -> None:
    page_hero(
        "기록하기",
        "OCR·검토·수기 입력을 한곳에서 처리합니다. 대시보드는 조회 전용입니다.",
        compact=True,
    )
    view = render_subnav(VIEWS, state_key="record_view", default="OCR")

    user, client = require_auth()
    ensure_profile(user, client)

    if view == "OCR":
        st.caption("잔고 · 매매 · 배당 · 부채 명세/납부 스크린샷 → AI 파싱 → 스테이징")
        render_ocr_upload(client, user)
    elif view == "검토":
        st.caption("표에서 확인하고 수정한 뒤 승인하면 DB에 반영됩니다.")
        render_staging_review(client, user)
    else:
        st.caption("매매 · 배당 · 현금 · 부채 · 세금을 직접 등록합니다.")
        tabs = st.tabs(["매매·배당·현금", "부채", "세금"])
        with tabs[0]:
            render_flow_forms(client, user)
        with tabs[1]:
            render_debt_forms(client, user)
        with tabs[2]:
            render_tax_forms(client, user)

    render_bottom_actions(enabled=True)


main()
