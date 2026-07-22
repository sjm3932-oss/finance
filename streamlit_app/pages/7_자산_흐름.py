"""Page: Record & review all asset flows (trades, dividends, cash, debt, PnL)."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth import ensure_profile, require_auth  # noqa: E402
from lib.ui_ko import (  # noqa: E402
    DEBT_TX_KO,
    FLOW_TYPE_KO,
    TRADE_TYPE_KO,
    localize_flow_df,
    rename_columns,
)

st.set_page_config(page_title="자산 흐름", layout="wide")

st.markdown(
    """
<style>
  .block-container { padding-top: 1rem; max-width: 1100px; }
  div.stButton > button { width: 100%; min-height: 2.6rem; }
</style>
""",
    unsafe_allow_html=True,
)

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


def tab_ledger(client) -> None:
    st.subheader("전체 흐름 원장")
    rows = (
        client.table("v_asset_flows")
        .select("*")
        .order("event_date", desc=True)
        .limit(300)
        .execute()
        .data
        or []
    )
    if not rows:
        st.info("아직 기록이 없습니다. 아래 탭에서 매매·배당·현금·부채를 입력하세요.")
        return

    kinds = sorted({r["flow_kind"] for r in rows})
    kind_labels = {
        "trade": "매매",
        "dividend": "배당",
        "cash_flow": "현금흐름",
        "debt": "부채",
    }
    pick = st.multiselect(
        "종류 필터",
        kinds,
        default=kinds,
        format_func=lambda k: kind_labels.get(k, k),
    )
    filtered = [r for r in rows if r["flow_kind"] in pick] if pick else rows
    df = localize_flow_df(filtered)
    show_cols = [
        c
        for c in [
            "발생일",
            "흐름종류",
            "세부유형",
            "자산/항목",
            "금액",
            "통화",
            "실현손익",
            "메모",
            "원천테이블",
        ]
        if c in df.columns
    ]
    st.dataframe(df[show_cols] if show_cols else df, use_container_width=True, hide_index=True)
    # Rough sum in mixed currencies — show separately (use original filtered rows)
    raw = pd.DataFrame(filtered)
    if "amount" in raw.columns:
        for ccy, g in raw.groupby(raw.get("currency", pd.Series(["KRW"] * len(raw)))):
            st.caption(f"{ccy} 합계(필터): {_fmt(g['amount'].sum(), ccy)}")


def tab_trade(client, user, accounts) -> None:
    st.subheader("매수 / 매도")
    if not accounts:
        st.warning("먼저 OCR 업로드에서 계좌를 만드세요.")
        return
    amap = {a["id"]: f"{a['institution']} ({a['currency']})" for a in accounts}
    with st.form("trade_form"):
        account_id = st.selectbox("계좌", options=list(amap), format_func=lambda i: amap[i])
        trade_type = st.selectbox(
            "구분",
            ["buy", "sell"],
            format_func=lambda x: TRADE_TYPE_KO.get(x, x),
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
        submitted = st.form_submit_button("매매 기록", type="primary")
    if submitted:
        if not ticker or quantity <= 0:
            st.error("티커와 수량을 확인하세요.")
            return
        try:
            row = {
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
            res = client.table("trades").insert(row).execute()
            created = (res.data or [None])[0]
            st.success(
                f"기록됨 · 실현손익={_fmt((created or {}).get('realized_pnl'), currency) if trade_type == 'sell' else '—'}"
            )
            st.rerun()
        except Exception as exc:
            st.error(f"실패: {exc}")

    recent = (
        client.table("trades")
        .select("trade_date,ticker,trade_type,price,quantity,fee,realized_pnl,currency,reason")
        .order("trade_date", desc=True)
        .limit(30)
        .execute()
        .data
        or []
    )
    st.dataframe(localize_flow_df(recent), use_container_width=True, hide_index=True)


def tab_dividend(client, user, accounts) -> None:
    st.subheader("배당금 입금")
    amap = {a["id"]: f"{a['institution']}" for a in accounts} if accounts else {}
    with st.form("div_form"):
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
        ok = st.form_submit_button("배당 기록", type="primary")
    if ok:
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
            st.success("배당 기록됨")
            st.rerun()
    rows = (
        client.table("dividends")
        .select("pay_date,ticker,name,amount,currency,memo")
        .order("pay_date", desc=True)
        .limit(40)
        .execute()
        .data
        or []
    )
    st.dataframe(rename_columns(pd.DataFrame(rows)), use_container_width=True, hide_index=True)


def tab_cash(client, user, accounts) -> None:
    st.subheader("현금 흐름 (수입/지출)")
    amap = {a["id"]: a["institution"] for a in accounts} if accounts else {}
    with st.form("cash_form"):
        flow_type = st.selectbox(
            "유형",
            ["income", "expense"],
            format_func=lambda x: FLOW_TYPE_KO.get(x, x),
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
        ok = st.form_submit_button("현금흐름 기록", type="primary")
    if ok:
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
            st.success("기록됨")
            st.rerun()
    rows = (
        client.table("cash_flows")
        .select("flow_date,flow_type,category,amount,currency,memo")
        .order("flow_date", desc=True)
        .limit(50)
        .execute()
        .data
        or []
    )
    st.dataframe(localize_flow_df(rows), use_container_width=True, hide_index=True)


def tab_debt(client, user) -> None:
    st.subheader("부채")
    with st.expander("부채 원장 등록", expanded=not _debts(client)):
        with st.form("debt_create"):
            lender = st.text_input("대출기관/상대", placeholder="주택담보대출")
            c1, c2 = st.columns(2)
            principal = c1.number_input("잔액(원)", min_value=0.0, step=100000.0, format="%.0f")
            rate = c2.number_input("금리(%)", min_value=0.0, step=0.1, format="%.2f")
            due = st.date_input("만기일 (모르면 오늘로 두고 메모에 표기)", value=date.today())
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
                    st.success("부채 등록됨")
                    st.rerun()

    debts = _debts(client)
    if not debts:
        st.info("등록된 부채가 없습니다.")
        return

    st.dataframe(rename_columns(pd.DataFrame(debts)), use_container_width=True, hide_index=True)
    dmap = {d["id"]: f"{d['lender']} (잔액 ₩{float(d['principal']):,.0f})" for d in debts}

    st.markdown("##### 부채 증감 기록")
    with st.form("debt_tx"):
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

    txs = (
        client.table("debt_transactions")
        .select("tx_date,tx_type,amount,memo,debt_id")
        .order("tx_date", desc=True)
        .limit(40)
        .execute()
        .data
        or []
    )
    st.dataframe(localize_flow_df(txs), use_container_width=True, hide_index=True)


def tab_pnl(client) -> None:
    st.subheader("실현손익 / 평가손익")
    realized = client.table("v_realized_pnl").select("*").execute().data or []
    unrealized = client.table("v_unrealized_pnl").select("*").execute().data or []

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**실현손익 (매도 기준)**")
        if realized:
            st.dataframe(rename_columns(pd.DataFrame(realized)), use_container_width=True, hide_index=True)
            # sum by currency
            df = pd.DataFrame(realized)
            for ccy, g in df.groupby("currency"):
                st.metric(f"실현합계 ({ccy})", _fmt(g["realized_pnl"].sum(), ccy))
        else:
            st.info("매도 기록이 있으면 실현손익이 표시됩니다.")
    with c2:
        st.markdown("**평가손익 (현재 보유)**")
        if unrealized:
            st.dataframe(rename_columns(pd.DataFrame(unrealized)), use_container_width=True, hide_index=True)
            df = pd.DataFrame(unrealized)
            total = pd.to_numeric(df.get("unrealized_pnl"), errors="coerce").sum()
            st.metric("평가손익 합계 (표시통화 단순합)", f"{total:,.2f}")
        else:
            st.info("보유 종목이 없습니다.")

    st.caption("평가손익은 시세 캐시 기준입니다. 대시보드에서 시세를 갱신하세요.")


def main() -> None:
    st.title("자산 흐름")
    st.caption("매매 · 배당 · 현금흐름 · 부채 · 실현/평가손익 — 모든 자산 흐름 기록")

    user, client = require_auth()
    ensure_profile(user, client)
    accounts = _accounts(client)

    tabs = st.tabs(["원장", "매매", "배당", "현금", "부채", "손익"])
    with tabs[0]:
        tab_ledger(client)
    with tabs[1]:
        tab_trade(client, user, accounts)
    with tabs[2]:
        tab_dividend(client, user, accounts)
    with tabs[3]:
        tab_cash(client, user, accounts)
    with tabs[4]:
        tab_debt(client, user)
    with tabs[5]:
        tab_pnl(client)


main()
