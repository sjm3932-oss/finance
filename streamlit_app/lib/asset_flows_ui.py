"""Ledger / transaction view (거래) — no realized-PnL charts (those live under 손익)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from lib.chart_period import filter_by_period, period_radio
from lib.theme import CHART_COLORS, PRIMARY, chart_layout, show_plotly
from lib.ui_ko import DEBT_TX_KO, FLOW_KIND_KO, FLOW_TYPE_KO, TRADE_TYPE_KO

CASH_INCOME_CATS = ["월급", "사업소득", "이자", "기타수입"]
CASH_EXPENSE_CATS = ["생활비", "주거", "식비", "교통", "보험", "세금납부", "이체/저축", "기타지출"]


def _accounts(client):
    return client.table("accounts").select("id,institution,account_type,currency").execute().data or []


def _debts(client):
    return client.table("debts").select("id,lender,principal,interest_rate").execute().data or []


def _fmt(n, ccy="KRW"):
    if n is None:
        return "—"
    try:
        v = float(n)
    except (TypeError, ValueError):
        return "—"
    return f"${v:,.2f}" if ccy == "USD" else f"₩{v:,.0f}"


def _load_flows(client, limit: int = 500) -> pd.DataFrame:
    rows = (
        client.table("v_asset_flows")
        .select("*")
        .order("event_date", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df["amount"] = pd.to_numeric(df.get("amount"), errors="coerce")
    df["flow_kind_ko"] = df["flow_kind"].map(
        lambda x: FLOW_KIND_KO.get(x, x) if isinstance(x, str) else x
    )
    return df


def render_flow_charts(client) -> None:
    """거래 원장: 기간 KPI + 월별 막대 1개 + 타임라인 표 (손익 차트 없음)."""
    months = period_radio(key="dash_period_trades", default="1년")
    df = filter_by_period(_load_flows(client), months, date_col="event_date")

    if df.empty:
        st.info("선택한 기간에 거래 기록이 없습니다. 「입력」에서 등록하세요.")
        return

    trade_n = int((df["flow_kind"] == "trade").sum())
    div_sum = float(df.loc[df["flow_kind"] == "dividend", "amount"].sum() or 0)
    subtype = df.get("flow_subtype")
    if subtype is not None:
        sub = subtype.astype(str)
        cash_in = float(
            df.loc[(df["flow_kind"] == "cash_flow") & sub.str.startswith("income"), "amount"].sum()
            or 0
        )
        cash_out = float(
            df.loc[(df["flow_kind"] == "cash_flow") & sub.str.startswith("expense"), "amount"].sum()
            or 0
        )
    else:
        cash_in = cash_out = 0.0

    k1, k2, k3, k4 = st.columns(4, gap="small")
    k1.metric("매매 건수", f"{trade_n:,}")
    k2.metric("배당 합계", _fmt(div_sum, "USD") if div_sum else "—")
    k3.metric("현금 수입", _fmt(cash_in, "KRW") if cash_in else "—")
    k4.metric("현금 지출", _fmt(cash_out, "KRW") if cash_out else "—")

    kinds = ["전체"] + sorted(
        [k for k in df["flow_kind_ko"].dropna().astype(str).unique().tolist() if k]
    )
    kind = st.radio("종류", kinds, horizontal=True, key="trade_kind_filter")
    view = df if kind == "전체" else df[df["flow_kind_ko"] == kind]

    # One monthly activity chart
    tmp = view.dropna(subset=["event_date"]).copy()
    if not tmp.empty:
        tmp["월"] = tmp["event_date"].dt.to_period("M").astype(str)
        monthly = (
            tmp.groupby(["월", "flow_kind_ko"], as_index=False)
            .size()
            .rename(columns={"size": "건수"})
        )
        fig = px.bar(
            monthly,
            x="월",
            y="건수",
            color="flow_kind_ko",
            color_discrete_sequence=CHART_COLORS,
            barmode="stack",
            labels={"flow_kind_ko": "종류"},
        )
        fig.update_layout(**chart_layout(240, with_title=True), title="월별 거래 건수", legend_title_text="")
        show_plotly(fig)

    # Timeline table (Toss-like ledger, not raw dump of every column)
    rows = view.sort_values("event_date", ascending=False).copy()
    display = pd.DataFrame(
        {
            "일자": rows["event_date"].dt.strftime("%Y-%m-%d"),
            "종류": rows["flow_kind_ko"],
            "종목/항목": rows.get("asset_ref", pd.Series([""] * len(rows))).fillna(""),
            "금액": rows["amount"],
            "통화": rows.get("currency", pd.Series(["KRW"] * len(rows))).fillna(""),
            "메모": rows.get("memo", pd.Series([""] * len(rows))).fillna("")
            if "memo" in rows.columns
            else "",
        }
    )
    st.caption(f"{len(display):,}건")
    st.dataframe(display, use_container_width=True, hide_index=True, height=420)


def _ocr_block(client, user, accounts, *, doc_type: str, key_prefix: str, label: str) -> None:
    """OCR upload block that stages to ocr_staging for later review/approve."""
    from lib.ocr_upload import stage_screenshot

    st.markdown(f"##### OCR로 {label}")
    st.caption("스크린샷을 올리면 스테이징으로 들어가고, **스테이징 검토**에서 승인하면 반영됩니다.")
    if not accounts:
        st.warning("먼저 계좌를 만들어 주세요. (OCR 업로드 또는 아래 안내)")
        return
    amap = {a["id"]: f"{a['institution']} ({a.get('currency', '')})" for a in accounts}
    account_id = st.selectbox(
        "대상 계좌",
        options=list(amap),
        format_func=lambda i: amap[i],
        key=f"{key_prefix}_ocr_account",
    )
    uploaded = st.file_uploader(
        f"{label} 스크린샷",
        type=["png", "jpg", "jpeg", "webp", "gif"],
        key=f"{key_prefix}_ocr_file",
    )
    if uploaded and st.button(f"OCR 파싱 · 스테이징", type="primary", key=f"{key_prefix}_ocr_go"):
        with st.spinner("이미지 저장 · AI 파싱 중…"):
            try:
                created, status, parsed, err = stage_screenshot(
                    client,
                    user_id=str(user.id),
                    account_id=account_id,
                    image_bytes=uploaded.getvalue(),
                    filename=uploaded.name,
                    mime_type=uploaded.type,
                    doc_type=doc_type,
                )
            except Exception as exc:
                st.error(f"실패: {exc}")
                return
        n_t = len(parsed.get("trades") or [])
        n_d = len(parsed.get("dividends") or [])
        n_h = len(parsed.get("holdings_snapshot") or [])
        if status == "failed":
            st.error(f"스테이징 실패: {err}")
        else:
            st.success(
                f"스테이징 완료 · 매매 {n_t} · 배당 {n_d} · 잔고 {n_h} "
                f"→ **스테이징 검토**에서 승인하세요."
            )


def render_flow_forms(client, user) -> None:
    """OCR + manual entry for trades/dividends; manual for cash/debt."""
    accounts = _accounts(client)
    st.info("매매·배당은 **OCR 스크린샷**과 **수기 입력**을 함께 사용할 수 있습니다.")
    tabs = st.tabs(["매매", "배당", "현금", "부채"])

    with tabs[0]:
        _ocr_block(client, user, accounts, doc_type="trades", key_prefix="trade", label="매매")
        st.divider()
        st.markdown("##### 수기로 매매 입력")
        if not accounts:
            st.warning("먼저 OCR 업로드에서 계좌를 만드세요.")
        else:
            amap = {a["id"]: f"{a['institution']} ({a['currency']})" for a in accounts}
            with st.form("dash_trade_form"):
                account_id = st.selectbox("계좌", options=list(amap), format_func=lambda i: amap[i])
                trade_type = st.selectbox(
                    "구분", ["buy", "sell"], format_func=lambda x: TRADE_TYPE_KO.get(x, x)
                )
                c1, c2 = st.columns(2)
                ticker = c1.text_input("티커", placeholder="TQQQ").strip().upper()
                trade_date = c2.date_input("일자", value=date.today())
                c3, c4, c5 = st.columns(3)
                price = c3.number_input("단가", min_value=0.0, step=0.01, format="%.4f")
                quantity = c4.number_input("수량", min_value=0.0, step=0.0001, format="%.6f")
                fee = c5.number_input("수수료", min_value=0.0, step=0.01, format="%.2f")
                currency = st.selectbox("통화", ["USD", "KRW"], index=0)
                reason = st.text_input("사유/메모", "")
                if st.form_submit_button("매매 기록", type="primary"):
                    if not ticker or quantity <= 0:
                        st.error("티커와 수량을 확인하세요.")
                    else:
                        try:
                            client.table("trades").insert(
                                {
                                    "account_id": account_id,
                                    "trade_date": trade_date.isoformat(),
                                    "ticker": ticker,
                                    "trade_type": trade_type,
                                    "price": price,
                                    "quantity": quantity,
                                    "fee": fee,
                                    "currency": currency,
                                    "reason": reason or None,
                                    "created_by": str(user.id),
                                    "adjust_holdings": True,
                                }
                            ).execute()
                            st.success("매매가 기록되었습니다.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"실패: {exc}")

    with tabs[1]:
        _ocr_block(client, user, accounts, doc_type="dividends", key_prefix="div", label="배당")
        st.divider()
        st.markdown("##### 수기로 배당 입력")
        amap = {a["id"]: a["institution"] for a in accounts} if accounts else {}
        with st.form("dash_div_form"):
            account_id = st.selectbox(
                "계좌 (선택)",
                options=[None] + list(amap),
                format_func=lambda i: "(없음)" if i is None else amap[i],
            )
            c1, c2 = st.columns(2)
            ticker = c1.text_input("티커", placeholder="TSLY").strip().upper()
            pay_date = c2.date_input("지급일", value=date.today())
            c3, c4 = st.columns(2)
            amount = c3.number_input("금액", min_value=0.0, step=1.0, format="%.2f")
            currency = c4.selectbox("통화", ["USD", "KRW"])
            name = st.text_input("종목명 (선택)", "")
            memo = st.text_input("메모", "")
            if st.form_submit_button("배당 기록", type="primary"):
                if not ticker or amount <= 0:
                    st.error("티커/금액을 확인하세요.")
                else:
                    client.table("dividends").insert(
                        {
                            "user_id": str(user.id),
                            "account_id": account_id,
                            "ticker": ticker,
                            "name": name or ticker,
                            "pay_date": pay_date.isoformat(),
                            "amount": amount,
                            "currency": currency,
                            "memo": memo or None,
                        }
                    ).execute()
                    st.success("배당이 기록되었습니다.")
                    st.rerun()

    with tabs[2]:
        amap = {a["id"]: a["institution"] for a in accounts} if accounts else {}
        with st.form("dash_cash_form"):
            flow_type = st.selectbox(
                "유형", ["income", "expense"], format_func=lambda x: FLOW_TYPE_KO.get(x, x)
            )
            cats = CASH_INCOME_CATS if flow_type == "income" else CASH_EXPENSE_CATS
            category = st.selectbox("카테고리", cats + ["직접입력"])
            custom = st.text_input("직접 카테고리", "") if category == "직접입력" else ""
            c1, c2, c3 = st.columns(3)
            amount = c1.number_input("금액", min_value=0.0, step=1000.0, format="%.0f")
            currency = c2.selectbox("통화", ["KRW", "USD"])
            flow_date = c3.date_input("일자", value=date.today())
            account_id = st.selectbox(
                "연결 계좌 (선택)",
                options=[None] + list(amap),
                format_func=lambda i: "(없음)" if i is None else amap[i],
            )
            memo = st.text_input("메모", "")
            if st.form_submit_button("현금흐름 기록", type="primary"):
                cat = custom.strip() if category == "직접입력" else category
                if not cat or amount <= 0:
                    st.error("카테고리/금액을 확인하세요.")
                else:
                    client.table("cash_flows").insert(
                        {
                            "user_id": str(user.id),
                            "flow_date": flow_date.isoformat(),
                            "category": cat,
                            "amount": amount,
                            "flow_type": flow_type,
                            "currency": currency,
                            "account_id": account_id,
                            "memo": memo or None,
                        }
                    ).execute()
                    st.success("기록되었습니다.")
                    st.rerun()

    with tabs[3]:
        with st.expander("부채 원장 등록", expanded=not _debts(client)):
            with st.form("dash_debt_create"):
                lender = st.text_input("대출기관/상대", placeholder="주택담보대출")
                c1, c2 = st.columns(2)
                principal = c1.number_input("잔액(원)", min_value=0.0, step=100000.0, format="%.0f")
                rate = c2.number_input("금리(%)", min_value=0.0, step=0.1, format="%.2f")
                due = st.date_input("만기일", value=date.today())
                no_due = st.checkbox("만기일 없음")
                memo = st.text_input("메모", "")
                if st.form_submit_button("부채 등록", type="primary"):
                    if not lender:
                        st.error("대출기관명을 입력하세요.")
                    else:
                        client.table("debts").insert(
                            {
                                "user_id": str(user.id),
                                "lender": lender,
                                "principal": principal,
                                "interest_rate": rate,
                                "due_date": None if no_due else due.isoformat(),
                                "memo": memo or None,
                            }
                        ).execute()
                        st.success("부채가 등록되었습니다.")
                        st.rerun()

        debts = _debts(client)
        if not debts:
            st.info("등록된 부채가 없습니다.")
        else:
            dmap = {
                d["id"]: f"{d['lender']} (잔액 ₩{float(d['principal']):,.0f})" for d in debts
            }
            ddf = pd.DataFrame(debts)
            ddf["principal"] = pd.to_numeric(ddf["principal"], errors="coerce")
            fig = px.pie(
                ddf,
                names="lender",
                values="principal",
                color_discrete_sequence=CHART_COLORS,
                hole=0.4,
            )
            fig.update_layout(**chart_layout(280, with_title=True), title="부채 구성")
            show_plotly(fig)

            with st.form("dash_debt_tx"):
                debt_id = st.selectbox("부채", options=list(dmap), format_func=lambda i: dmap[i])
                tx_type = st.selectbox(
                    "유형",
                    ["increase", "repayment", "decrease", "interest"],
                    format_func=lambda x: DEBT_TX_KO.get(x, x),
                )
                c1, c2 = st.columns(2)
                amount = c1.number_input("금액", min_value=0.0, step=10000.0, format="%.0f")
                tx_date = c2.date_input("일자", value=date.today())
                memo = st.text_input("메모", "")
                if st.form_submit_button("부채 거래 기록", type="primary"):
                    if amount <= 0:
                        st.error("금액을 확인하세요.")
                    else:
                        try:
                            client.table("debt_transactions").insert(
                                {
                                    "debt_id": debt_id,
                                    "user_id": str(user.id),
                                    "tx_date": tx_date.isoformat(),
                                    "tx_type": tx_type,
                                    "amount": amount,
                                    "memo": memo or None,
                                }
                            ).execute()
                            st.success("기록됨 (잔액 자동 반영)")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))
