"""Asset-flow charts + compact entry forms (used inside Dashboard)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

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


def _load_flows(client, limit: int = 400) -> pd.DataFrame:
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
    df["realized_pnl"] = pd.to_numeric(df.get("realized_pnl"), errors="coerce")
    df["flow_kind_ko"] = df["flow_kind"].map(lambda x: FLOW_KIND_KO.get(x, x) if isinstance(x, str) else x)
    return df


def render_flow_charts(client) -> None:
    """Chart-first overview of trades / dividends / cash / debt / PnL."""
    df = _load_flows(client)
    realized = client.table("v_realized_pnl").select("*").execute().data or []
    unrealized = client.table("v_unrealized_pnl").select("*").execute().data or []

    if df.empty and not realized and not unrealized:
        st.info("아직 자산 흐름 기록이 없습니다. 「기록하기」에서 입력하세요.")
        return

    # KPI strip
    if not df.empty:
        trade_n = int((df["flow_kind"] == "trade").sum())
        div_sum = df.loc[df["flow_kind"] == "dividend", "amount"].sum()
        cash_in = df.loc[(df["flow_kind"] == "cash_flow") & (df["flow_subtype"].astype(str).str.startswith("income")), "amount"].sum()
        cash_out = df.loc[(df["flow_kind"] == "cash_flow") & (df["flow_subtype"].astype(str).str.startswith("expense")), "amount"].sum()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("매매 건수", f"{trade_n:,}")
        k2.metric("배당 합계", _fmt(div_sum, "USD") if div_sum else "—")
        k3.metric("현금 수입", _fmt(cash_in, "KRW") if cash_in else "—")
        k4.metric("현금 지출", _fmt(cash_out, "KRW") if cash_out else "—")

    if not df.empty:
        c1, c2 = st.columns(2)
        with c1:
            kind_counts = (
                df.dropna(subset=["flow_kind_ko"])
                .groupby("flow_kind_ko", as_index=False)
                .size()
                .rename(columns={"size": "건수"})
            )
            if not kind_counts.empty:
                fig = px.pie(
                    kind_counts,
                    names="flow_kind_ko",
                    values="건수",
                    color_discrete_sequence=CHART_COLORS,
                    hole=0.45,
                )
                fig.update_layout(**chart_layout(260), title="흐름 구성")
                show_plotly(fig)
        with c2:
            # Monthly activity (count)
            tmp = df.dropna(subset=["event_date"]).copy()
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
                )
                fig.update_layout(**chart_layout(260), title="월별 활동", legend_title_text="")
                show_plotly(fig)

        # Amount trend for cash + dividends (by currency separately if needed)
        money = df[df["flow_kind"].isin(["dividend", "cash_flow", "debt"])].dropna(subset=["event_date", "amount"])
        if not money.empty:
            money = money.sort_values("event_date")
            money["종류"] = money["flow_kind_ko"]
            fig = px.bar(
                money.tail(60),
                x="event_date",
                y="amount",
                color="종류",
                color_discrete_sequence=CHART_COLORS,
                labels={"event_date": "일자", "amount": "금액"},
            )
            fig.update_layout(**chart_layout(280), title="최근 입출금·배당·부채")
            show_plotly(fig)

        trades = df[df["flow_kind"] == "trade"].dropna(subset=["asset_ref", "amount"])
        if not trades.empty:
            by_ticker = (
                trades.groupby("asset_ref", as_index=False)["amount"]
                .sum()
                .sort_values("amount", ascending=False)
                .head(12)
            )
            fig = px.bar(
                by_ticker,
                x="asset_ref",
                y="amount",
                color_discrete_sequence=[PRIMARY],
                labels={"asset_ref": "티커", "amount": "거래대금"},
            )
            fig.update_layout(**chart_layout(280), title="종목별 거래대금")
            show_plotly(fig)

    # PnL charts
    p1, p2 = st.columns(2)
    with p1:
        if realized:
            rdf = pd.DataFrame(realized)
            rdf["realized_pnl"] = pd.to_numeric(rdf.get("realized_pnl"), errors="coerce")
            if "ticker" in rdf.columns:
                g = rdf.groupby("ticker", as_index=False)["realized_pnl"].sum().sort_values("realized_pnl")
                fig = go.Figure(
                    go.Bar(
                        x=g["realized_pnl"],
                        y=g["ticker"],
                        orientation="h",
                        marker_color=[PRIMARY if v >= 0 else "#FF6B6B" for v in g["realized_pnl"]],
                    )
                )
                fig.update_layout(**chart_layout(280), title="실현손익 (종목)", xaxis_title="손익")
                show_plotly(fig)
            total = rdf["realized_pnl"].sum()
            st.caption(f"실현손익 합계(표시통화 단순합): {total:,.2f}")
        else:
            st.info("실현손익 데이터가 없습니다.")
    with p2:
        if unrealized:
            udf = pd.DataFrame(unrealized)
            udf["unrealized_pnl"] = pd.to_numeric(udf.get("unrealized_pnl"), errors="coerce")
            if "ticker" in udf.columns:
                g = udf.groupby("ticker", as_index=False)["unrealized_pnl"].sum().sort_values("unrealized_pnl")
                fig = go.Figure(
                    go.Bar(
                        x=g["unrealized_pnl"],
                        y=g["ticker"],
                        orientation="h",
                        marker_color=[PRIMARY if v >= 0 else "#FF6B6B" for v in g["unrealized_pnl"]],
                    )
                )
                fig.update_layout(**chart_layout(280), title="평가손익 (종목)", xaxis_title="손익")
                show_plotly(fig)
            total = udf["unrealized_pnl"].sum()
            st.caption(f"평가손익 합계(표시통화 단순합): {total:,.2f}")
        else:
            st.info("평가손익 데이터가 없습니다.")


def render_flow_forms(client, user) -> None:
    """Compact entry forms for trades / dividends / cash / debt."""
    accounts = _accounts(client)
    tabs = st.tabs(["매매", "배당", "현금", "부채"])

    with tabs[0]:
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
            # Debt composition chart
            ddf = pd.DataFrame(debts)
            ddf["principal"] = pd.to_numeric(ddf["principal"], errors="coerce")
            fig = px.pie(
                ddf,
                names="lender",
                values="principal",
                color_discrete_sequence=CHART_COLORS,
                hole=0.4,
            )
            fig.update_layout(**chart_layout(260), title="부채 구성")
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
