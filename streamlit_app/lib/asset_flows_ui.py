"""Ledger / transaction view (거래) — no realized-PnL charts (those live under 손익)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from lib.account_filter import filter_df_by_account_ids
from lib.chart_period import filter_by_period, period_radio
from lib.export_csv import download_csv_button
from lib.theme import PRIMARY, chart_layout, show_plotly
from lib.ui_ko import FLOW_KIND_KO, FLOW_TYPE_KO, TRADE_TYPE_KO

CASH_INCOME_CATS = ["월급", "사업소득", "이자", "증권입금", "예수금이자", "기타수입"]
CASH_EXPENSE_CATS = [
    "생활비",
    "주거",
    "식비",
    "교통",
    "보험",
    "세금납부",
    "이체/저축",
    "증권출금",
    "기타지출",
]
BROKER_CASH_CATS = ["증권입금", "증권출금", "예수금이자"]


def _accounts(client):
    return client.table("accounts").select("id,institution,account_type,currency").execute().data or []



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


def render_flow_charts(
    client,
    *,
    account_ids: list[str] | None = None,
    account_label: str = "전체",
) -> None:
    """거래 원장: 자금 유입·유출(금액) + 타임라인. 실현손익 차트는 손익 탭."""
    months = period_radio(key="dash_period_trades", default="1년")
    df = filter_by_period(_load_flows(client), months, date_col="event_date")
    df = filter_df_by_account_ids(df, account_ids, col="account_id")

    if df.empty:
        label = f"{account_label} · " if account_label and account_label != "전체" else ""
        from lib.ux import empty_cta

        empty_cta(
            f"{label}선택한 기간에 거래 기록이 없습니다. 「기록하기」에서 등록하세요.",
            button_label="기록하기로 이동",
            page_title="기록하기",
            key="cta_trades_empty",
        )
        return

    # v_asset_flows.amount is already signed (buy/expense/repayment negative).
    work = df.dropna(subset=["event_date"]).copy()
    work["amount"] = pd.to_numeric(work["amount"], errors="coerce").fillna(0.0)
    work["유입"] = work["amount"].clip(lower=0)
    work["유출"] = (-work["amount"]).clip(lower=0)

    # ---- Enhanced filters ----
    f1, f2, f3 = st.columns([1.2, 1.2, 1.4], gap="small")
    kinds = ["전체"] + sorted(
        [k for k in work["flow_kind_ko"].dropna().astype(str).unique().tolist() if k]
    )
    with f1:
        kind = st.selectbox("종류", kinds, key="trade_kind_filter")
    with f2:
        direction = st.selectbox(
            "방향", ["전체", "유입", "유출"], key="trade_dir_filter"
        )
    with f3:
        q = st.text_input(
            "검색",
            placeholder="종목·티커·메모",
            key="trade_search_q",
        )

    d1, d2 = st.columns(2, gap="small")
    min_d = work["event_date"].min().date()
    max_d = work["event_date"].max().date()
    with d1:
        start = st.date_input("시작일", value=min_d, key="trade_start")
    with d2:
        end = st.date_input("종료일", value=max_d, key="trade_end")

    view = work
    if kind != "전체":
        view = view[view["flow_kind_ko"] == kind]
    if direction == "유입":
        view = view[view["amount"] > 0]
    elif direction == "유출":
        view = view[view["amount"] < 0]
    if start:
        view = view[view["event_date"].dt.date >= start]
    if end:
        view = view[view["event_date"].dt.date <= end]
    if q and q.strip():
        qq = q.strip().lower()
        ref = view.get("asset_ref", pd.Series([""] * len(view))).fillna("").astype(str)
        memo = (
            view.get("memo", pd.Series([""] * len(view))).fillna("").astype(str)
            if "memo" in view.columns
            else pd.Series([""] * len(view))
        )
        mask = ref.str.lower().str.contains(qq, regex=False) | memo.str.lower().str.contains(
            qq, regex=False
        )
        view = view[mask]

    if view.empty:
        st.info("필터 조건에 맞는 거래가 없습니다.")
        return

    inflow = float(view["유입"].sum())
    outflow = float(view["유출"].sum())
    net = inflow - outflow
    trade_n = int((view["flow_kind"] == "trade").sum()) if "flow_kind" in view.columns else 0

    k1, k2, k3, k4 = st.columns(4, gap="small")
    k1.metric("유입", _fmt(inflow, "KRW") if inflow else "—")
    k2.metric("유출", _fmt(outflow, "KRW") if outflow else "—")
    k3.metric("순이동", _fmt(net, "KRW") if (inflow or outflow) else "—")
    k4.metric("매매 건수", f"{trade_n:,}")

    # Broker deposit/withdrawal spotlight
    if "asset_ref" in view.columns or "flow_subtype" in view.columns:
        cat_col = None
        for cand in ("flow_subtype", "asset_ref", "memo"):
            if cand in view.columns:
                cat_col = cand
                break
        if cat_col:
            broker_mask = view[cat_col].astype(str).apply(
                lambda s: any(b in s for b in BROKER_CASH_CATS)
            )
            broker = view[broker_mask]
            if not broker.empty:
                dep = float(broker.loc[broker["amount"] > 0, "amount"].sum())
                wdr = float((-broker.loc[broker["amount"] < 0, "amount"]).sum())
                st.caption(
                    f"증권 입출금 · 입금 {_fmt(dep, 'KRW')} · 출금 {_fmt(wdr, 'KRW')}"
                )

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
            chart_layout(
                240,
                title="월별 자금 이동",
                legend_title_text="",
            )
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
    from lib.ui_ko import show_dataframe

    st.caption(f"{len(display):,}건 · 통화 혼합 합계는 참고용(손익 탭과 별개)")
    show_dataframe(display, use_container_width=True, hide_index=True, height=420)
    download_csv_button(display, filename_prefix="trades", key="export_trades_tab_csv")


def render_flow_forms(client, user) -> None:
    """Manual entry only — OCR lives under 기록하기 → OCR tab."""
    accounts = _accounts(client)
    st.caption("수기 입력입니다. 스크린샷 파싱은 「OCR」 탭을 사용하세요.")
    tabs = st.tabs(["매매", "배당", "현금"])

    with tabs[0]:
        st.markdown("##### 매매 입력")
        if not accounts:
            st.warning("먼저 「OCR」 탭에서 계좌를 만드세요.")
        else:
            amap = {a["id"]: f"{a['institution']} ({a['currency']})" for a in accounts}
            with st.form("dash_trade_form"):
                account_id = st.selectbox(
                    "계좌", options=list(amap), format_func=lambda i: amap[i]
                )
                trade_type = st.selectbox(
                    "구분",
                    ["buy", "sell"],
                    format_func=lambda x: TRADE_TYPE_KO.get(x, x),
                )
                ticker = st.text_input("티커", placeholder="TQQQ").strip().upper()
                trade_date = st.date_input("일자", value=date.today())
                quantity = st.number_input(
                    "수량", min_value=0.0, step=0.0001, format="%.6f"
                )
                price = st.number_input(
                    "단가", min_value=0.0, step=0.01, format="%.4f"
                )
                fee = st.number_input("수수료", min_value=0.0, step=0.01, format="%.2f")
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
            ticker = st.text_input("티커", placeholder="TSLY").strip().upper()
            name = st.text_input("종목명 (선택)", "")
            pay_date = st.date_input("지급일", value=date.today())
            amount = st.number_input("금액", min_value=0.0, step=1.0, format="%.2f")
            currency = st.selectbox("통화", ["USD", "KRW"])
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
        st.caption(
            "증권 입출금은 카테고리 「증권입금」「증권출금」「예수금이자」를 사용하세요."
        )
        with st.form("dash_cash_form"):
            flow_type = st.selectbox(
                "유형",
                ["income", "expense"],
                format_func=lambda x: FLOW_TYPE_KO.get(x, x),
            )
            cats = CASH_INCOME_CATS if flow_type == "income" else CASH_EXPENSE_CATS
            category = st.selectbox("카테고리", cats + ["직접입력"])
            custom = (
                st.text_input("직접 카테고리", "") if category == "직접입력" else ""
            )
            amount = st.number_input("금액", min_value=0.0, step=1000.0, format="%.0f")
            currency = st.selectbox("통화", ["KRW", "USD"])
            flow_date = st.date_input("일자", value=date.today())
            account_id = st.selectbox(
                "연결 계좌 (증권 입출금 시 권장)",
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
