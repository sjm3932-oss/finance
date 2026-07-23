"""Unified write path: OCR upload → staging review → manual entry."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from lib.ocr_upload import DOC_TYPES, stage_screenshot
from lib.ui_ko import ACCOUNT_TYPE_KO, STATUS_KO

# Display columns (Korean) → JSON keys
_TRADE_COLS = {
    "일자": "trade_date",
    "티커": "ticker",
    "종목명": "name",
    "구분": "trade_type",
    "단가": "price",
    "수량": "quantity",
    "수수료": "fee",
    "통화": "currency",
    "메모": "reason",
}
_DIV_COLS = {
    "지급일": "pay_date",
    "티커": "ticker",
    "종목명": "name",
    "금액": "amount",
    "통화": "currency",
    "메모": "memo",
}
_HOLD_COLS = {
    "티커": "ticker",
    "종목명": "name",
    "수량": "quantity",
    "평단": "avg_price",
    "통화": "currency",
}
_DEBT_COLS = {
    "대출명": "lender",
    "종류": "debt_kind",
    "잔금": "balance",
    "최초원금": "original_principal",
    "이자율": "interest_rate",
    "만기일": "due_date",
    "메모": "memo",
}
_PAY_COLS = {
    "납부일": "pay_date",
    "대출명": "lender",
    "납부액": "amount",
    "이자": "interest_portion",
    "원금상환": "principal_portion",
    "납부후잔금": "balance_after",
    "적용금리": "rate",
    "메모": "memo",
}


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


def _counts(parsed: dict) -> dict[str, int]:
    return {
        "trades": len(parsed.get("trades") or []),
        "dividends": len(parsed.get("dividends") or []),
        "holdings": len(parsed.get("holdings_snapshot") or []),
        "debts": len(parsed.get("debts") or []),
        "debt_payments": len(parsed.get("debt_payments") or []),
    }


def _rows_to_df(rows: list[dict] | None, col_map: dict[str, str]) -> pd.DataFrame:
    keys = list(col_map.values())
    labels = list(col_map.keys())
    data = []
    for row in rows or []:
        data.append({label: row.get(key) for label, key in col_map.items()})
    if not data:
        return pd.DataFrame(columns=labels)
    return pd.DataFrame(data, columns=labels)


def _df_to_rows(df: pd.DataFrame | None, col_map: dict[str, str]) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    out: list[dict[str, Any]] = []
    for _, series in df.iterrows():
        item: dict[str, Any] = {}
        empty = True
        for label, key in col_map.items():
            val = series.get(label)
            if pd.isna(val):
                val = None
            elif hasattr(val, "item"):
                try:
                    val = val.item()
                except Exception:
                    val = str(val)
            if isinstance(val, str):
                val = val.strip()
                if val == "":
                    val = None
            if val is not None:
                empty = False
            item[key] = val
        if not empty:
            out.append(item)
    return out


def _editor(title: str, df: pd.DataFrame, key: str) -> pd.DataFrame:
    st.markdown(f"##### {title}")
    if df.empty:
        st.caption("항목 없음 — 행을 추가할 수 있습니다.")
    return st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=key,
    )


def render_ocr_upload(client, user) -> None:
    """Screenshot → Gemini OCR → ocr_staging."""
    accounts_resp = client.table("accounts").select("id, institution, account_type, currency").execute()
    accounts = accounts_resp.data or []

    with st.expander("계좌 만들기 (증권/은행 업로드 시 필요)", expanded=not accounts):
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

    default_doc = st.session_state.pop("record_ocr_pref_doc", None)
    doc_keys = list(DOC_TYPES.keys())
    doc_index = doc_keys.index(default_doc) if default_doc in doc_keys else 0
    doc_type = st.selectbox(
        "문서 종류",
        options=doc_keys,
        format_func=lambda k: DOC_TYPES[k],
        index=doc_index,
        help="부채 명세·월 납부 내역도 OCR로 올릴 수 있습니다.",
        key="record_ocr_doc_type",
    )

    debt_only = doc_type == "debt"
    selected_account: str | None = None

    if debt_only:
        st.caption(
            "부채 OCR은 대출 잔금·이자율·원리금 납부 내역을 읽습니다. "
            "승인 시 대출명으로 기존 부채에 매칭하거나 새로 등록합니다."
        )
        if accounts:
            account_labels = {
                a["id"]: (
                    f"{a['institution']} "
                    f"({ACCOUNT_TYPE_KO.get(a['account_type'], a['account_type'])}, {a['currency']})"
                )
                for a in accounts
            }
            options = [None] + list(account_labels.keys())
            selected_account = st.selectbox(
                "연결 계좌 (선택)",
                options=options,
                format_func=lambda i: "(없음)" if i is None else account_labels[i],
                key="record_ocr_account_debt",
            )
    else:
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

    uploaded = st.file_uploader(
        "스크린샷 (잔고 / 매매 / 배당 / 부채)",
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

        c = _counts(parsed_json)
        if status == "failed":
            st.error(f"실패로 스테이징됨: {error_msg}. 「검토」에서 표를 수정해 승인하세요.")
        else:
            st.success(
                "대기로 스테이징됨 · "
                f"매매 {c['trades']} · 배당 {c['dividends']} · 잔고 {c['holdings']} · "
                f"부채 {c['debts']} · 납부 {c['debt_payments']} "
                f"(`{created['id'] if created else '완료'}`)"
            )
        st.info("다음: 사이드바 **승인하기**에서 표로 확인하고 승인하세요.")


def render_staging_review(client, user) -> None:
    """Review OCR staging with editable tables (not raw JSON)."""
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

    st.write(
        f"**상태:** `{STATUS_KO.get(row['status'], row['status'])}` · "
        f"업로더 `{str(row['uploaded_by'])[:8]}…`"
    )

    url = _signed_url(client, row["image_url"])
    if url:
        st.image(url, caption="업로드된 스크린샷", use_container_width=True)

    parsed = row.get("parsed_json") or {}
    if isinstance(parsed, str):
        parsed = json.loads(parsed)

    c = _counts(parsed)
    st.caption(
        f"매매 {c['trades']} · 배당 {c['dividends']} · 잔고 {c['holdings']} · "
        f"부채 {c['debts']} · 납부 {c['debt_payments']}"
    )

    accounts = client.table("accounts").select("id, institution").execute().data or []
    account_ids = [a["id"] for a in accounts]
    account_map = {a["id"]: a["institution"] for a in accounts}
    needs_account = bool(c["trades"] or c["dividends"] or c["holdings"])

    current_account = parsed.get("account_id")
    account_id = None
    if needs_account:
        if not account_ids:
            st.error("계좌가 없습니다. 「OCR」탭에서 계좌를 먼저 만드세요.")
            return
        if current_account not in account_ids:
            current_account = account_ids[0]
        account_id = st.selectbox(
            "반영 계좌",
            options=account_ids,
            index=account_ids.index(current_account),
            format_func=lambda i: f"{account_map.get(i, i)}",
            key=f"review_account_{selected_id}",
        )
    elif account_ids:
        options = [None] + account_ids
        idx = options.index(current_account) if current_account in account_ids else 0
        account_id = st.selectbox(
            "계좌 (선택)",
            options=options,
            index=idx,
            format_func=lambda i: "(없음)" if i is None else account_map.get(i, i),
            key=f"review_account_opt_{selected_id}",
        )

    if c["debts"] or c["debt_payments"]:
        existing = (
            client.table("debts").select("lender,principal,interest_rate").order("lender").execute().data
            or []
        )
        if existing:
            with st.expander("기존 부채 (대출명 매칭 참고)", expanded=False):
                st.dataframe(
                    pd.DataFrame(
                        {
                            "대출명": [d["lender"] for d in existing],
                            "잔금": [d["principal"] for d in existing],
                            "이자율": [d["interest_rate"] for d in existing],
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

    sid = selected_id[:8]
    edited_trades = _editor(
        "매매",
        _rows_to_df(parsed.get("trades"), _TRADE_COLS),
        key=f"ed_trades_{sid}",
    )
    edited_divs = _editor(
        "배당",
        _rows_to_df(parsed.get("dividends"), _DIV_COLS),
        key=f"ed_divs_{sid}",
    )
    edited_holds = _editor(
        "잔고/보유",
        _rows_to_df(parsed.get("holdings_snapshot"), _HOLD_COLS),
        key=f"ed_holds_{sid}",
    )
    edited_debts = _editor(
        "부채 명세",
        _rows_to_df(parsed.get("debts"), _DEBT_COLS),
        key=f"ed_debts_{sid}",
    )
    edited_pays = _editor(
        "부채 납부",
        _rows_to_df(parsed.get("debt_payments"), _PAY_COLS),
        key=f"ed_pays_{sid}",
    )

    st.caption("표에서 값을 고친 뒤 승인하면 수정본이 반영됩니다. 행 추가/삭제도 가능합니다.")

    col1, col2, col3 = st.columns(3)
    approve = col1.button("승인 및 반영", type="primary", key=f"btn_approve_{sid}")
    reject = col2.button("반려", key=f"btn_reject_{sid}")
    save_only = col3.button("수정만 저장", key=f"btn_save_{sid}")

    if not (approve or reject or save_only):
        return

    edited = {
        "account_id": account_id,
        "doc_type": parsed.get("doc_type"),
        "account_hint": parsed.get("account_hint"),
        "trades": _df_to_rows(edited_trades, _TRADE_COLS),
        "dividends": _df_to_rows(edited_divs, _DIV_COLS),
        "holdings_snapshot": _df_to_rows(edited_holds, _HOLD_COLS),
        "debts": _df_to_rows(edited_debts, _DEBT_COLS),
        "debt_payments": _df_to_rows(edited_pays, _PAY_COLS),
    }

    if needs_account and not account_id:
        st.error("매매·배당·잔고 반영에는 계좌가 필요합니다.")
        st.stop()

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

    # Clear editor widget state for this staging id so next load is fresh
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and k.endswith(f"_{sid}") and k.startswith("ed_"):
            del st.session_state[k]

    if approve:
        st.success("승인됨. 표 내용이 DB에 반영되었습니다.")
        st.rerun()
    elif reject:
        st.warning("반려되었습니다.")
        st.rerun()
    else:
        st.success("수정 내용이 저장되었습니다.")
        st.rerun()
