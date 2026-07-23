"""Ledger / transaction view (거래) — no realized-PnL charts (those live under 손익)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from lib.chart_period import filter_by_period, period_radio
from lib.theme import CHART_COLORS, PRIMARY, chart_layout, show_plotly
from lib.ui_ko import FLOW_KIND_KO, FLOW_TYPE_KO, TRADE_TYPE_KO

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
    """거래 원장: 자금 유입·유출(금액) + 타임라인. 실현손익 차트는 손익 탭."""
    months = period_radio(key="dash_period_trades", default="1년")
    df = filter_by_period(_load_flows(client), months, date_col="event_date")

    if df.empty:
        st.info("선택한 기간에 거래 기록이 없습니다. 「기록하기」에서 등록하세요.")
        return

    # v_asset_flows.amount is already signed (buy/expense/repayment negative).
    work = df.dropna(subset=["event_date"]).copy()
    work["amount"] = pd.to_numeric(work["amount"], errors="coerce").fillna(0.0)
    work["유입"] = work["amount"].clip(lower=0)
    work["유출"] = (-work["amount"]).clip(lower=0)

    inflow = float(work["유입"].sum())
    outflow = float(work["유출"].sum())
    net = inflow - outflow
    trade_n = int((work["flow_kind"] == "trade").sum())

    k1, k2, k3, k4 = st.columns(4, gap="small")
    k1.metric("유입", _fmt(inflow, "KRW") if inflow else "—")
    k2.metric("유출", _fmt(outflow, "KRW") if outflow else "—")
    k3.metric("순이동", _fmt(net, "KRW") if (inflow or outflow) else "—")
    k4.metric("매매 건수", f"{trade_n:,}")

    kinds = ["전체"] + sorted(
        [k for k in work["flow_kind_ko"].dropna().astype(str).unique().tolist() if k]
    )
    kind = st.radio("종류", kinds, horizontal=True, key="trade_kind_filter")
    view = work if kind == "전체" else work[work["flow_kind_ko"] == kind]

    tmp = view.copy()
    if not tmp.empty:
        tmp["월"] = tmp["event_date"].dt.to_period("M").astype(str)
        monthly = (
            tmp.groupby("월", as_index=False)
            .agg(유입=("유입", "sum"), 유출=("유출", "sum"))
            .sort_values("월")
        )
        melt = monthly.melt(
            id_vars="월", value_vars=["유입", "유출"], var_name="구분", value_name="금액"
        )
        fig = px.bar(
            melt,
            x="월",
            y="금액",
            color="구분",
            barmode="group",
            color_discrete_map={"유입": PRIMARY, "유출": "#94A3B8"},
            labels={"금액": "금액"},
        )
        fig.update_layout(
            **chart_layout(240, with_title=True),
            title="월별 자금 이동",
            legend_title_text="",
        )
        show_plotly(fig)

    rows = view.sort_values("event_date", ascending=False).copy()
    display = pd.DataFrame(
        {
            "일자": rows["event_date"].dt.strftime("%Y-%m-%d"),
            "종류": rows["flow_kind_ko"],
            "종목/항목": rows.get("asset_ref", pd.Series([""] * len(rows))).fillna(""),
            "금액": rows["amount"].abs(),
            "방향": rows["amount"].map(
                lambda x: "유입" if x > 0 else ("유출" if x < 0 else "—")
            ),
            "통화": rows.get("currency", pd.Series(["KRW"] * len(rows))).fillna(""),
            "메모": rows.get("memo", pd.Series([""] * len(rows))).fillna("")
            if "memo" in rows.columns
            else "",
        }
    )
    st.caption(f"{len(display):,}건 · 통화 혼합 합계는 참고용(손익 탭과 별개)")
    st.dataframe(display, use_container_width=True, hide_index=True, height=420)


def render_flow_forms(client, user) -> None:
    """Manual entry only — OCR lives under 기록하기 → OCR tab."""
    accounts = _accounts(client)
    st.caption("수기 입력입니다. 스크린샷 파싱은 「OCR」 탭을 사용하세요.")
    tabs = st.tabs(["매매", "배당", "현금", "부채"])

    with tabs[0]:
        st.markdown("##### 매매 입력")
        if not accounts:
            st.warning("먼저 「OCR」 탭에서 계좌를 만드세요.")
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
        st.markdown("##### 배당 입력")
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
        st.info(
            "부채 등록·원리금 납부·이자율 변경은 **대시보드 → 부채**에서 관리합니다. "
            "이자는 잔금 기준으로 자동 계산됩니다."
        )
        debts = _debts(client)
        if debts:
            ddf = pd.DataFrame(debts)
            ddf["principal"] = pd.to_numeric(ddf["principal"], errors="coerce")
            fig = px.pie(
                ddf,
                names="lender",
                values="principal",
                color_discrete_sequence=CHART_COLORS,
                hole=0.4,
            )
            fig.update_layout(**chart_layout(280, with_title=True), title="부채 잔금 구성")
            show_plotly(fig)
            if st.button("대시보드 부채로 이동", key="goto_debt_dash"):
                st.session_state["dash_view"] = "부채"
                st.switch_page("pages/1_대시보드.py")
