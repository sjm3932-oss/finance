"""Page: Upload screenshot → Gemini OCR → ocr_staging."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth import ensure_profile, require_auth  # noqa: E402
from lib.ocr_upload import DOC_TYPES, stage_screenshot  # noqa: E402
from lib.theme import apply_theme, page_hero  # noqa: E402
from lib.ui_ko import ACCOUNT_TYPE_KO  # noqa: E402

st.set_page_config(page_title="OCR 업로드", page_icon="💚", layout="wide")
apply_theme(max_width=1120)


def main() -> None:
    page_hero("OCR 업로드", "잔고 · 매매 · 배당 스크린샷 → AI 파싱 → 스테이징")

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

    doc_type = st.selectbox(
        "문서 종류",
        options=list(DOC_TYPES.keys()),
        format_func=lambda k: DOC_TYPES[k],
        index=0,
        help="매매·배당·잔고를 각각 찍어도 되고, 자동 인식도 가능합니다.",
    )

    uploaded = st.file_uploader(
        "스크린샷 (잔고 / 매매 / 배당)",
        type=["png", "jpg", "jpeg", "webp", "gif"],
    )

    if uploaded and st.button("파싱 및 스테이징", type="primary"):
        with st.spinner("이미지 저장 · AI 파싱 중…"):
            try:
                created, status, parsed_json, error_msg = stage_screenshot(
                    client,
                    user_id=str(user.id),
                    account_id=selected_account,
                    image_bytes=uploaded.getvalue(),
                    filename=uploaded.name,
                    mime_type=uploaded.type,
                    doc_type=doc_type,
                )
            except Exception as exc:
                st.error(f"업로드/파싱 실패: {exc}")
                st.stop()

        n_trades = len(parsed_json.get("trades") or [])
        n_divs = len(parsed_json.get("dividends") or [])
        n_hold = len(parsed_json.get("holdings_snapshot") or [])

        if status == "failed":
            st.error(f"실패로 스테이징됨: {error_msg}. 다시 업로드하거나 스테이징에서 수정하세요.")
        else:
            st.success(
                f"대기로 스테이징됨 · 매매 {n_trades} · 배당 {n_divs} · 잔고 {n_hold} "
                f"(`{created['id'] if created else '완료'}`)"
            )

        st.subheader("파싱 결과")
        st.code(json.dumps(parsed_json, ensure_ascii=False, indent=2), language="json")
        st.info("다음: **스테이징 검토**에서 확인 후 승인하세요. 매매·배당도 OCR과 수기 입력을 함께 쓸 수 있습니다.")


main()
