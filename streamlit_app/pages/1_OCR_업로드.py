"""Page: Upload screenshot → Gemini OCR → ocr_staging."""

from __future__ import annotations

import json
import mimetypes
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth import ensure_profile, require_auth  # noqa: E402
from lib.gemini_client import GeminiError, parse_screenshot  # noqa: E402
from lib.ui_ko import ACCOUNT_TYPE_KO  # noqa: E402
from lib.theme import apply_theme, page_hero  # noqa: E402


st.set_page_config(page_title="OCR 업로드", page_icon="💚", layout="wide")
apply_theme(max_width=900)


def main() -> None:
    page_hero("OCR 업로드", "스크린샷 → AI 파싱 → 스테이징(대기/실패)")
    st.caption("스크린샷 → AI 파싱 → 스테이징(대기/실패)")

    user, client = require_auth()
    ensure_profile(user, client)

    accounts_resp = client.table("accounts").select("id, institution, account_type, currency").execute()
    accounts = accounts_resp.data or []

    with st.expander("계좌 만들기 (승인 전 필요)", expanded=not accounts):
        with st.form("create_account"):
            institution = st.text_input("금융기관", placeholder="토스증권")
            account_type = st.selectbox(
                "계좌유형",
                ["brokerage", "bank", "loan"],
                format_func=lambda x: ACCOUNT_TYPE_KO.get(x, x),
            )
            currency = st.selectbox("통화", ["KRW", "USD"])
            if st.form_submit_button("계좌 생성"):
                if not institution.strip():
                    st.error("금융기관명을 입력하세요")
                else:
                    client.table("accounts").insert(
                        {
                            "user_id": str(user.id),
                            "institution": institution.strip(),
                            "account_type": account_type,
                            "currency": currency,
                        }
                    ).execute()
                    st.success("계좌가 생성되었습니다")
                    st.rerun()

    if not accounts:
        st.info("계좌를 하나 만든 뒤 업로드하세요. (승인 시 계좌 선택이 필요합니다)")
        return

    account_labels = {
        a["id"]: (
            f"{a['institution']} "
            f"({ACCOUNT_TYPE_KO.get(a['account_type'], a['account_type'])}, {a['currency']})"
        )
        for a in accounts
    }
    selected_account = st.selectbox(
        "이 업로드의 대상 계좌",
        options=list(account_labels.keys()),
        format_func=lambda i: account_labels[i],
    )

    uploaded = st.file_uploader(
        "잔고 / 매매 스크린샷",
        type=["png", "jpg", "jpeg", "webp", "gif"],
    )

    if uploaded and st.button("파싱 및 스테이징", type="primary"):
        image_bytes = uploaded.getvalue()
        mime = uploaded.type or mimetypes.guess_type(uploaded.name)[0] or "image/png"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        object_path = f"{user.id}/{stamp}_{uuid.uuid4().hex}_{uploaded.name}"

        with st.spinner("이미지 저장 중…"):
            storage = client.storage.from_("ocr-screenshots")
            try:
                storage.upload(
                    object_path,
                    image_bytes,
                    file_options={"content-type": mime, "upsert": "false"},
                )
            except Exception as exc:
                st.error(f"이미지 저장 실패: {exc}")
                st.stop()
            image_url = object_path

        parsed_json = {
            "account_id": selected_account,
            "trades": [],
            "holdings_snapshot": [],
        }
        status = "pending"
        error_msg = None

        with st.spinner("AI 파싱 중…"):
            try:
                parsed = parse_screenshot(image_bytes, mime_type=mime)
                parsed["account_id"] = selected_account
                parsed_json = parsed
                if (
                    parsed.get("error") == "unreadable"
                    and not parsed.get("trades")
                    and not parsed.get("holdings_snapshot")
                ):
                    status = "failed"
                    error_msg = "Gemini가 스크린샷을 읽을 수 없습니다"
            except GeminiError as exc:
                status = "failed"
                error_msg = str(exc)
                parsed_json = {
                    "account_id": selected_account,
                    "trades": [],
                    "holdings_snapshot": [],
                    "error": str(exc),
                }

        row = {
            "uploaded_by": str(user.id),
            "image_url": image_url,
            "parsed_json": parsed_json,
            "status": status,
        }
        insert = client.table("ocr_staging").insert(row).execute()
        created = (insert.data or [None])[0]

        if status == "failed":
            st.error(f"실패로 스테이징됨: {error_msg}. 다시 업로드하거나 나중에 수정하세요.")
        else:
            st.success(f"대기로 스테이징됨: `{created['id'] if created else '완료'}`")

        st.subheader("파싱 결과")
        st.code(json.dumps(parsed_json, ensure_ascii=False, indent=2), language="json")
        st.info("다음: **스테이징 검토** 페이지에서 검토 후 승인하세요.")


main()
