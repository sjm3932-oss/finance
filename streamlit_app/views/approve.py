"""승인하기 — OCR 스테이징 표 검토·수정·승인."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth import ensure_profile, require_auth  # noqa: E402
from lib.record_ui import render_staging_review  # noqa: E402
from lib.theme import apply_theme, page_hero  # noqa: E402

apply_theme(max_width=1120)


def main() -> None:
    page_hero(
        "승인하기",
        "OCR로 올라온 데이터를 표에서 확인하고, 수정한 뒤 승인합니다.",
        compact=True,
    )
    user, client = require_auth()
    ensure_profile(user, client)
    render_staging_review(client, user)


main()
