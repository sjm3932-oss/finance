"""Unified write path: OCR upload → staging review → manual entry."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from lib.ocr_upload import DOC_TYPES, stage_screenshot
from lib.ui_ko import ACCOUNT_TYPE_KO, STATUS_KO, localize_flow_df, rename_columns


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


def render_ocr_upload(client, user) -> None:
    """Screenshot → Gemini OCR → ocr_staging."""
    accounts_resp = client.table("accounts").select("id, institution, account_type, currency").execute()
    accounts = accounts_resp.data or []

    with st.expander("계좌 만들기 (승인 전 필요)", expanded=not accounts):
        with st.form("create_account_record"):
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
        key="record_ocr_account",
    )

    doc_type = st.selectbox(
        "문서 종류",
        options=list(DOC_TYPES.keys()),
        format_func=lambda k: DOC_TYPES[k],
        index=0,
        help="매매·배당·잔고를 각각 찍어도 되고, 자동 인식도 가능합니다.",
        key="record_ocr_doc_type",
    )

    uploaded = st.file_uploader(
        "스크린샷 (잔고 / 매매 / 배당)",
        type=["png", "jpg", "jpeg", "webp", "gif"],
        key="record_ocr_file",
    )

    if uploaded and st.button("파싱 및 스테이징", type="primary", key="record_ocr_submit"):
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
            st.error(f"실패로 스테이징됨: {error_msg}. 다시 업로드하거나 「검토」에서 수정하세요.")
        else:
            st.success(
                f"대기로 스테이징됨 · 매매 {n_trades} · 배당 {n_divs} · 잔고 {n_hold} "
                f"(`{created['id'] if created else '완료'}`)"
            )

        st.subheader("파싱 결과")
        st.code(json.dumps(parsed_json, ensure_ascii=False, indent=2), language="json")
        st.info("다음: 상단 **검토**에서 확인 후 승인하세요. 수기 입력은 **수기** 탭을 사용하세요.")


def render_staging_review(client, user) -> None:
    """Review / edit / approve ocr_staging rows."""
    status_filter = st.multiselect(
        "상태 필터",
        options=["pending", "failed", "approved", "rejected"],
        default=["pending", "failed"],
        format_func=lambda x: STATUS_KO.get(x, x),
        key="record_staging_status",
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
        st.info("표시할 스테이징 항목이 없습니다. 「OCR」에서 먼저 업로드하세요.")
        return

    labels = {
        r["id"]: f"{r['created_at']} · {STATUS_KO.get(r['status'], r['status'])} · {r['id'][:8]}"
        for r in rows
    }
    selected_id = st.selectbox(
        "스테이징 항목",
        options=list(labels.keys()),
        format_func=lambda i: labels[i],
        key="record_staging_pick",
    )
    row = next(r for r in rows if r["id"] == selected_id)

    st.write(f"**이미지 경로:** `{row['image_url']}`")
    st.write(
        f"**상태:** `{STATUS_KO.get(row['status'], row['status'])}` · "
        f"업로더 `{row['uploaded_by']}`"
    )

    url = _signed_url(client, row["image_url"])
    if url:
        st.image(url, caption="업로드된 스크린샷", use_container_width=True)
    else:
        st.caption("미리보기를 사용할 수 없습니다 (서명 URL을 만들 수 없음).")

    parsed = row.get("parsed_json") or {}
    if isinstance(parsed, str):
        parsed = json.loads(parsed)

    accounts = client.table("accounts").select("id, institution").execute().data or []
    account_ids = [a["id"] for a in accounts]
    account_map = {a["id"]: a["institution"] for a in accounts}

    with st.form("record_review_form"):
        current_account = parsed.get("account_id")
        if current_account not in account_ids and account_ids:
            current_account = account_ids[0]
        account_id = st.selectbox(
            "계좌",
            options=account_ids or [""],
            index=(account_ids.index(current_account) if current_account in account_ids else 0),
            format_func=lambda i: f"{account_map.get(i, i)} ({i})",
        )
        json_text = st.text_area(
            "파싱 결과 (수정 가능)",
            value=json.dumps(parsed, ensure_ascii=False, indent=2),
            height=360,
        )
        col1, col2, col3 = st.columns(3)
        approve = col1.form_submit_button("승인 및 반영", type="primary")
        reject = col2.form_submit_button("반려")
        save_only = col3.form_submit_button("수정만 저장 (상태 유지)")

    if not (approve or reject or save_only):
        return

    try:
        edited = json.loads(json_text)
    except json.JSONDecodeError as exc:
        st.error(f"잘못된 JSON: {exc}")
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
        st.error(f"업데이트 실패 (트리거가 승인을 롤백했을 수 있음): {exc}")
        st.stop()

    if approve:
        st.success("승인됨. 매매·배당·보유 확인 중…")
        trades = (
            client.table("trades")
            .select("id, ticker, trade_type, quantity, price, trade_date, created_at")
            .eq("account_id", account_id)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
            .data
        )
        dividends = (
            client.table("dividends")
            .select("pay_date,ticker,name,amount,currency,memo,created_at")
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
        st.subheader("최근 매매")
        st.dataframe(localize_flow_df(trades or []), use_container_width=True)
        st.subheader("최근 배당")
        st.dataframe(rename_columns(pd.DataFrame(dividends or [])), use_container_width=True)
        st.subheader("보유")
        st.dataframe(rename_columns(pd.DataFrame(holdings or [])), use_container_width=True)
    elif reject:
        st.warning("반려되었습니다.")
    else:
        st.success("수정 내용이 저장되었습니다.")
