"""Page: Review / edit / approve ocr_staging rows."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth import ensure_profile, require_auth  # noqa: E402

st.set_page_config(page_title="Review Staging", layout="wide")


def _signed_url(client, path: str) -> str | None:
    try:
        signed = client.storage.from_("ocr-screenshots").create_signed_url(path, 3600)
    except Exception:
        return None

    if isinstance(signed, str):
        return signed
    if hasattr(signed, "signed_url") and signed.signed_url:
        return signed.signed_url
    if isinstance(signed, dict):
        for key in ("signedURL", "signedUrl", "signed_url"):
            if signed.get(key):
                return signed[key]
        data = signed.get("data")
        if isinstance(data, dict):
            for key in ("signedURL", "signedUrl", "signed_url"):
                if data.get(key):
                    return data[key]
    return None


def main() -> None:
    st.title("Review Staging")
    st.caption(
        "Human-in-the-loop: pending/failed 항목을 수정하고 승인하면 trades/holdings에 커밋됩니다."
    )

    user, client = require_auth()
    ensure_profile(user, client)

    status_filter = st.multiselect(
        "Status filter",
        options=["pending", "failed", "approved", "rejected"],
        default=["pending", "failed"],
    )
    query = (
        client.table("ocr_staging")
        .select("*")
        .order("created_at", desc=True)
        .limit(50)
    )
    if status_filter:
        query = query.in_("status", status_filter)
    rows = query.execute().data or []

    if not rows:
        st.info("표시할 스테이징 항목이 없습니다.")
        return

    labels = {
        r["id"]: f"{r['created_at']} · {r['status']} · {r['id'][:8]}"
        for r in rows
    }
    selected_id = st.selectbox(
        "Staging row",
        options=list(labels.keys()),
        format_func=lambda i: labels[i],
    )
    row = next(r for r in rows if r["id"] == selected_id)

    st.write(f"**Image path:** `{row['image_url']}`")
    st.write(f"**Status:** `{row['status']}` · uploaded_by `{row['uploaded_by']}`")

    url = _signed_url(client, row["image_url"])
    if url:
        st.image(url, caption="Uploaded screenshot", use_container_width=True)
    else:
        st.caption("Preview unavailable (signed URL could not be created).")

    parsed = row.get("parsed_json") or {}
    if isinstance(parsed, str):
        parsed = json.loads(parsed)

    accounts = client.table("accounts").select("id, institution").execute().data or []
    account_ids = [a["id"] for a in accounts]
    account_map = {a["id"]: a["institution"] for a in accounts}

    with st.form("review_form"):
        current_account = parsed.get("account_id")
        if current_account not in account_ids and account_ids:
            current_account = account_ids[0]
        account_id = st.selectbox(
            "account_id",
            options=account_ids or [""],
            index=(account_ids.index(current_account) if current_account in account_ids else 0),
            format_func=lambda i: f"{account_map.get(i, i)} ({i})",
        )
        json_text = st.text_area(
            "parsed_json (editable)",
            value=json.dumps(parsed, ensure_ascii=False, indent=2),
            height=360,
        )
        col1, col2, col3 = st.columns(3)
        approve = col1.form_submit_button("Approve & commit", type="primary")
        reject = col2.form_submit_button("Reject")
        save_only = col3.form_submit_button("Save edits (keep status)")

    if not (approve or reject or save_only):
        return

    try:
        edited = json.loads(json_text)
    except json.JSONDecodeError as exc:
        st.error(f"Invalid JSON: {exc}")
        st.stop()

    edited["account_id"] = account_id
    payload = {
        "parsed_json": edited,
        "reviewed_by": str(user.id),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    if approve:
        payload["status"] = "approved"
    elif reject:
        payload["status"] = "rejected"

    try:
        client.table("ocr_staging").update(payload).eq("id", selected_id).execute()
    except Exception as exc:
        st.error(f"Update failed (trigger may have rolled back approval): {exc}")
        st.stop()

    if approve:
        st.success("Approved. Checking trades/holdings…")
        trades = (
            client.table("trades")
            .select("id, ticker, trade_type, quantity, price, trade_date, created_at")
            .eq("account_id", account_id)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
            .data
        )
        holdings = (
            client.table("holdings")
            .select("ticker, name, quantity, avg_price, currency, updated_at")
            .eq("account_id", account_id)
            .execute()
            .data
        )
        st.subheader("Recent trades")
        st.dataframe(trades or [], use_container_width=True)
        st.subheader("Holdings")
        st.dataframe(holdings or [], use_container_width=True)
    elif reject:
        st.warning("Rejected.")
    else:
        st.success("Saved edits.")


main()
