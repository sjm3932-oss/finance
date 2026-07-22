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

st.set_page_config(page_title="Upload OCR", layout="wide")


def main() -> None:
    st.title("Upload OCR")
    st.caption("스크린샷 → Gemini Vision → ocr_staging (pending/failed)")

    user, client = require_auth()
    ensure_profile(user, client)

    accounts_resp = client.table("accounts").select("id, institution, account_type, currency").execute()
    accounts = accounts_resp.data or []

    with st.expander("Create account (required before approve)", expanded=not accounts):
        with st.form("create_account"):
            institution = st.text_input("Institution", placeholder="토스증권")
            account_type = st.selectbox("Type", ["brokerage", "bank", "loan"])
            currency = st.selectbox("Currency", ["KRW", "USD"])
            if st.form_submit_button("Create account"):
                if not institution.strip():
                    st.error("Institution required")
                else:
                    client.table("accounts").insert(
                        {
                            "user_id": str(user.id),
                            "institution": institution.strip(),
                            "account_type": account_type,
                            "currency": currency,
                        }
                    ).execute()
                    st.success("Account created")
                    st.rerun()

    if not accounts:
        st.info("계좌를 하나 만든 뒤 업로드하세요. (승인 시 account_id 필요)")
        return

    account_labels = {
        a["id"]: f"{a['institution']} ({a['account_type']}, {a['currency']})"
        for a in accounts
    }
    selected_account = st.selectbox(
        "Target account for this upload",
        options=list(account_labels.keys()),
        format_func=lambda i: account_labels[i],
    )

    uploaded = st.file_uploader(
        "Balance / trade screenshot",
        type=["png", "jpg", "jpeg", "webp", "gif"],
    )

    if uploaded and st.button("Parse & stage", type="primary"):
        image_bytes = uploaded.getvalue()
        mime = uploaded.type or mimetypes.guess_type(uploaded.name)[0] or "image/png"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        object_path = f"{user.id}/{stamp}_{uuid.uuid4().hex}_{uploaded.name}"

        with st.spinner("Uploading to Storage…"):
            storage = client.storage.from_("ocr-screenshots")
            try:
                storage.upload(
                    object_path,
                    image_bytes,
                    file_options={"content-type": mime, "upsert": "false"},
                )
            except Exception as exc:
                st.error(f"Storage upload failed: {exc}")
                st.stop()
            image_url = object_path

        parsed_json = {
            "account_id": selected_account,
            "trades": [],
            "holdings_snapshot": [],
        }
        status = "pending"
        error_msg = None

        with st.spinner("Calling Gemini Vision…"):
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
                    error_msg = "Gemini could not read the screenshot"
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
            st.error(f"Staged as failed: {error_msg}. Re-upload or edit later.")
        else:
            st.success(f"Staged as pending: `{created['id'] if created else 'ok'}`")

        st.subheader("Parsed JSON")
        st.code(json.dumps(parsed_json, ensure_ascii=False, indent=2), language="json")
        st.info("다음: **Review Staging** 페이지에서 검토 후 승인하세요.")


main()
