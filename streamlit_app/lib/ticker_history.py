"""종목 상세: 매매·배당 이력."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from lib.export_csv import download_csv_button
from lib.ui_ko import TRADE_TYPE_KO


def _fmt(n, ccy="KRW"):
    if n is None:
        return "—"
    try:
        v = float(n)
    except (TypeError, ValueError):
        return "—"
    return f"${v:,.2f}" if ccy == "USD" else f"₩{v:,.0f}"


def render_ticker_history(
    client,
    ticker: str,
    *,
    account_ids: list[str] | None = None,
) -> None:
    """Show trades + dividends for one ticker (optionally account-scoped)."""
    trades_q = (
        client.table("trades")
        .select(
            "trade_date,trade_type,price,quantity,fee,currency,realized_pnl,reason,account_id"
        )
        .eq("ticker", ticker)
        .order("trade_date", desc=True)
        .limit(200)
    )
    trades = trades_q.execute().data or []
    if account_ids is not None:
        allow = {str(a) for a in account_ids}
        trades = [t for t in trades if str(t.get("account_id") or "") in allow]

    divs_q = (
        client.table("dividends")
        .select("pay_date,amount,currency,name,memo,account_id")
        .eq("ticker", ticker)
        .order("pay_date", desc=True)
        .limit(200)
    )
    divs = divs_q.execute().data or []
    if account_ids is not None:
        allow = {str(a) for a in account_ids}
        divs = [d for d in divs if str(d.get("account_id") or "") in allow]

    st.markdown("##### 매매 이력")
    if not trades:
        st.caption("이 종목의 매매 기록이 없습니다.")
    else:
        tdf = pd.DataFrame(
            {
                "일자": [t.get("trade_date") for t in trades],
                "구분": [
                    TRADE_TYPE_KO.get(t.get("trade_type"), t.get("trade_type"))
                    for t in trades
                ],
                "단가": [t.get("price") for t in trades],
                "수량": [t.get("quantity") for t in trades],
                "수수료": [t.get("fee") for t in trades],
                "실현손익": [t.get("realized_pnl") for t in trades],
                "통화": [t.get("currency") for t in trades],
                "메모": [t.get("reason") or "" for t in trades],
            }
        )
        st.dataframe(tdf, use_container_width=True, hide_index=True, height=260)
        download_csv_button(
            tdf, filename_prefix=f"trades_{ticker}", key=f"export_trades_{ticker}"
        )

    st.markdown("##### 배당 이력")
    if not divs:
        st.caption("이 종목의 배당 기록이 없습니다.")
    else:
        ddf = pd.DataFrame(
            {
                "지급일": [d.get("pay_date") for d in divs],
                "금액": [d.get("amount") for d in divs],
                "통화": [d.get("currency") for d in divs],
                "메모": [d.get("memo") or "" for d in divs],
            }
        )
        st.dataframe(ddf, use_container_width=True, hide_index=True, height=220)
        download_csv_button(
            ddf, filename_prefix=f"divs_{ticker}", key=f"export_divs_{ticker}"
        )
