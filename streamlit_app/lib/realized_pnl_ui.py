"""Combined realized P&L charts (trades + dividends + interest).

Supports account filtering and daily (trade-ledger) or monthly views.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.chart_period import filter_by_period, period_radio
from lib.export_csv import download_csv_button
from lib.theme import CHART_COLORS, PRIMARY, apply_chart_layout, show_plotly
from lib.ui_ko import PNL_KIND_KO

KIND_COLORS = {
    "매매실현": PRIMARY,
    "배당": "#FFB800",
    "이자수입": "#00A3FF",
    "이자비용": "#FF6B6B",
}

KIND_ORDER = ["매매실현", "배당", "이자수입", "이자비용"]


def _usdkrw(client) -> float | None:
    try:
        rows = (
            client.table("market_prices")
            .select("price")
            .eq("ticker", "USDKRW")
            .limit(1)
            .execute()
            .data
            or []
        )
        if rows:
            return float(rows[0]["price"])
    except Exception:
        pass
    return None


def _ids_set(account_ids: list[str] | None) -> set[str] | None:
    if account_ids is None:
        return None
    return {str(a) for a in account_ids}


def load_total_realized(
    client, account_ids: list[str] | None = None
) -> pd.DataFrame:
    """Build realized PnL rows from source tables (supports account filter)."""
    allow = _ids_set(account_ids)
    rows: list[dict] = []

    sells = (
        client.table("trades")
        .select(
            "id,trade_date,ticker,realized_pnl,currency,account_id,price,quantity,fee"
        )
        .eq("trade_type", "sell")
        .execute()
        .data
        or []
    )
    for t in sells:
        if t.get("realized_pnl") is None:
            continue
        aid = str(t.get("account_id") or "")
        if allow is not None and aid not in allow:
            continue
        rows.append(
            {
                "event_date": t.get("trade_date"),
                "pnl_kind": "trade_realized",
                "asset_ref": t.get("ticker") or "",
                "asset_name": t.get("ticker") or "",
                "pnl": float(t.get("realized_pnl") or 0),
                "currency": (t.get("currency") or "KRW"),
                "account_id": aid,
                "source_table": "trades",
                "source_id": t.get("id"),
                "detail": (
                    f"매도 {t.get('quantity')}주 @ {t.get('price')}"
                    if t.get("quantity") is not None
                    else "매도"
                ),
            }
        )

    dividends = (
        client.table("dividends")
        .select("id,pay_date,ticker,name,amount,currency,account_id")
        .execute()
        .data
        or []
    )
    for d in dividends:
        if d.get("amount") is None:
            continue
        aid = str(d.get("account_id") or "")
        if allow is not None and aid not in allow:
            continue
        rows.append(
            {
                "event_date": d.get("pay_date"),
                "pnl_kind": "dividend",
                "asset_ref": d.get("ticker") or "",
                "asset_name": d.get("name") or d.get("ticker") or "",
                "pnl": float(d.get("amount") or 0),
                "currency": (d.get("currency") or "KRW"),
                "account_id": aid,
                "source_table": "dividends",
                "source_id": d.get("id"),
                "detail": "배당",
            }
        )

    cash = (
        client.table("cash_flows")
        .select("id,flow_date,flow_type,category,amount,currency,account_id")
        .eq("flow_type", "income")
        .execute()
        .data
        or []
    )
    for c in cash:
        cat = str(c.get("category") or "")
        if "이자" not in cat and "interest" not in cat.lower():
            continue
        aid = str(c.get("account_id") or "")
        if allow is not None and aid not in allow:
            continue
        rows.append(
            {
                "event_date": c.get("flow_date"),
                "pnl_kind": "interest_income",
                "asset_ref": cat or "이자",
                "asset_name": cat or "이자",
                "pnl": float(c.get("amount") or 0),
                "currency": (c.get("currency") or "KRW"),
                "account_id": aid,
                "source_table": "cash_flows",
                "source_id": c.get("id"),
                "detail": "이자수입",
            }
        )

    try:
        debts = (
            client.table("debts")
            .select("id,lender,account_id")
            .execute()
            .data
            or []
        )
    except Exception:
        debts = client.table("debts").select("id,lender").execute().data or []
    debt_map = {str(d["id"]): d for d in debts}
    txs = (
        client.table("debt_transactions")
        .select("id,debt_id,tx_date,tx_type,amount,interest_portion")
        .eq("tx_type", "interest")
        .execute()
        .data
        or []
    )
    for tx in txs:
        debt = debt_map.get(str(tx.get("debt_id") or "")) or {}
        aid = str(debt.get("account_id") or "")
        if allow is not None:
            # Unlinked debts only appear under 전체
            if not aid or aid not in allow:
                continue
        amt = tx.get("interest_portion")
        if amt is None:
            amt = tx.get("amount")
        rows.append(
            {
                "event_date": tx.get("tx_date"),
                "pnl_kind": "interest_expense",
                "asset_ref": debt.get("lender") or "부채",
                "asset_name": debt.get("lender") or "부채",
                "pnl": -abs(float(amt or 0)),
                "currency": "KRW",
                "account_id": aid,
                "source_table": "debt_transactions",
                "source_id": tx.get("id"),
                "detail": "이자비용",
            }
        )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce").fillna(0.0)
    df["currency"] = df["currency"].fillna("KRW").astype(str).str.upper()
    df["pnl_kind_ko"] = df["pnl_kind"].map(lambda x: PNL_KIND_KO.get(x, x))
    df["asset_ref"] = df["asset_ref"].fillna("기타").astype(str)
    df["asset_name"] = df["asset_name"].fillna(df["asset_ref"]).astype(str)
    rate = _usdkrw(client) or 0.0
    df["pnl_krw"] = df.apply(
        lambda r: float(r["pnl"]) * rate
        if r["currency"] == "USD" and rate
        else float(r["pnl"]),
        axis=1,
    )
    if rate <= 0:
        df.loc[df["currency"] == "USD", "pnl_krw"] = pd.NA
    return df


def _fmt(v: float, *, use_krw: bool) -> str:
    if pd.isna(v):
        return "—"
    return f"{v:,.0f}" if use_krw else f"{v:,.2f}"


def _value_setup(df: pd.DataFrame, client) -> tuple[str, str, bool, float | None]:
    rate = _usdkrw(client)
    use_krw = df["pnl_krw"].notna().any()
    value_col = "pnl_krw" if use_krw else "pnl"
    unit = "원" if use_krw else "표시통화"
    return value_col, unit, use_krw, rate


def _kpi_row(df: pd.DataFrame, value_col: str, unit: str, *, use_krw: bool) -> None:
    total = float(df[value_col].sum(skipna=True) or 0)
    by_kind = (
        df.groupby("pnl_kind_ko", as_index=False)[value_col]
        .sum()
        .set_index("pnl_kind_ko")[value_col]
    )
    kind_labels = [k for k in KIND_ORDER if k in by_kind.index] + [
        k for k in by_kind.index if k not in KIND_ORDER
    ]
    cols = st.columns(min(5, max(2, len(kind_labels) + 1)))
    cols[0].metric(f"기간 실현손익 ({unit})", _fmt(total, use_krw=use_krw))
    for i, kind in enumerate(kind_labels, start=1):
        if i >= len(cols):
            break
        cols[i].metric(kind, _fmt(float(by_kind[kind]), use_krw=use_krw))


def _ticker_options(df: pd.DataFrame) -> list[str]:
    mask = df["pnl_kind"].isin(["trade_realized", "dividend"])
    refs = (
        df.loc[mask, "asset_ref"]
        .dropna()
        .astype(str)
        .loc[lambda s: ~s.isin(["", "기타", "nan"])]
        .unique()
        .tolist()
    )
    return sorted(refs)


def _chart_monthly_by_kind(df: pd.DataFrame, value_col: str, unit: str, *, height: int) -> None:
    tmp = df.dropna(subset=["event_date"]).copy()
    if tmp.empty:
        st.info("선택한 기간에 실현손익이 없습니다.")
        return
    tmp["월"] = tmp["event_date"].dt.to_period("M").astype(str)
    monthly_kind = (
        tmp.groupby(["월", "pnl_kind_ko"], as_index=False)[value_col]
        .sum()
        .sort_values("월")
    )
    color_map = {**KIND_COLORS}
    extras = [c for c in CHART_COLORS if c not in KIND_COLORS.values()]
    for i, lab in enumerate(sorted(monthly_kind["pnl_kind_ko"].unique())):
        if lab not in color_map:
            color_map[lab] = extras[i % len(extras)] if extras else PRIMARY

    fig = go.Figure()
    for kind in KIND_ORDER + [
        k for k in monthly_kind["pnl_kind_ko"].unique() if k not in KIND_ORDER
    ]:
        part = monthly_kind[monthly_kind["pnl_kind_ko"] == kind]
        if part.empty:
            continue
        fig.add_trace(
            go.Bar(
                x=part["월"],
                y=part[value_col],
                name=kind,
                marker_color=color_map.get(kind, PRIMARY),
            )
        )
    fig.update_layout(barmode="relative")
    apply_chart_layout(
        fig,
        height,
        title="월별 실현손익 (종류별)",
        yaxis_title=unit,
        xaxis_title="월",
    )
    show_plotly(fig)


def _chart_daily(df: pd.DataFrame, value_col: str, unit: str, *, height: int) -> None:
    tmp = df.dropna(subset=["event_date"]).copy()
    if tmp.empty:
        st.info("선택한 기간에 일자별 손익이 없습니다.")
        return
    tmp["일자"] = tmp["event_date"].dt.strftime("%Y-%m-%d")
    daily = (
        tmp.groupby("일자", as_index=False)[value_col]
        .sum()
        .sort_values("일자")
    )
    colors = [PRIMARY if v >= 0 else "#FF6B6B" for v in daily[value_col]]
    fig = go.Figure(
        go.Bar(
            x=daily["일자"],
            y=daily[value_col],
            marker_color=colors,
            name="일별 실현손익",
        )
    )
    apply_chart_layout(
        fig,
        height,
        title="일자별 실현손익",
        yaxis_title=unit,
        xaxis_title="일자",
        showlegend=False,
    )
    show_plotly(fig)


def _table_by_ticker(df: pd.DataFrame, value_col: str, *, use_krw: bool) -> None:
    tmp = df[df["pnl_kind"].isin(["trade_realized", "dividend"])].copy()
    if tmp.empty:
        st.caption("종목별 실현 기록이 없습니다.")
        return
    tmp["표시명"] = tmp.apply(
        lambda r: r["asset_name"]
        if r.get("asset_name") and r["asset_name"] != r["asset_ref"]
        else r["asset_ref"],
        axis=1,
    )
    pivot = (
        tmp.groupby(["asset_ref", "표시명", "pnl_kind_ko"], as_index=False)[value_col]
        .sum()
    )
    wide = (
        pivot.pivot_table(
            index=["asset_ref", "표시명"],
            columns="pnl_kind_ko",
            values=value_col,
            aggfunc="sum",
            fill_value=0.0,
        )
        .reset_index()
    )
    wide["합계"] = wide.drop(columns=["asset_ref", "표시명"]).sum(axis=1)
    wide = wide.sort_values("합계", ascending=False)
    disp = wide.rename(columns={"표시명": "종목", "asset_ref": "티커"}).copy()
    for c in disp.columns:
        if c in ("종목", "티커"):
            continue
        disp[c] = disp[c].map(lambda v: _fmt(float(v), use_krw=use_krw))
    st.dataframe(disp, use_container_width=True, hide_index=True)


def _table_daily_ledger(df: pd.DataFrame, value_col: str, *, use_krw: bool) -> None:
    """Day-by-day PnL ledger from trade/dividend/interest events."""
    tmp = df.dropna(subset=["event_date"]).copy()
    if tmp.empty:
        st.caption("일자별 내역이 없습니다.")
        return
    tmp = tmp.sort_values(["event_date", "pnl_kind"], ascending=[False, True])
    tmp["일자"] = tmp["event_date"].dt.strftime("%Y-%m-%d")

    daily_sum = (
        tmp.groupby("일자", as_index=False)[value_col]
        .sum()
        .rename(columns={value_col: "일합계"})
        .sort_values("일자", ascending=False)
    )

    st.markdown("##### 일자별 합계")
    sum_disp = daily_sum.copy()
    sum_disp["일합계"] = sum_disp["일합계"].map(lambda v: _fmt(float(v), use_krw=use_krw))
    st.dataframe(sum_disp, use_container_width=True, hide_index=True, height=220)

    st.markdown("##### 건별 내역 (거래·배당·이자)")
    detail = pd.DataFrame(
        {
            "일자": tmp["일자"],
            "구분": tmp["pnl_kind_ko"],
            "종목": tmp["asset_name"],
            "티커": tmp["asset_ref"],
            "손익": tmp[value_col].map(lambda v: _fmt(float(v), use_krw=use_krw)),
            "통화": tmp["currency"],
            "내용": tmp["detail"].fillna("") if "detail" in tmp.columns else "",
        }
    )
    st.dataframe(detail, use_container_width=True, hide_index=True, height=420)


def render_total_realized_pnl(
    client,
    *,
    compact: bool = False,
    account_ids: list[str] | None = None,
    account_label: str = "전체",
) -> None:
    """손익: 계좌 필터 + 월별/일자별 실현손익."""
    df_all = load_total_realized(client, account_ids=account_ids)
    if df_all.empty:
        label = account_label if account_label != "전체" else ""
        st.info(
            f"{label + ' · ' if label else ''}"
            "실현손익 데이터가 없습니다. 매도·배당·이자가 쌓이면 여기에 표시됩니다."
        )
        return

    value_col, unit, use_krw, rate = _value_setup(df_all, client)
    if use_krw and rate:
        st.caption(f"환율 {rate:,.2f}원 환산")
    elif (df_all["currency"] == "USD").any() and not use_krw:
        st.caption("환율 없음 · 통화별 단순합")

    key = "realized_pnl_period_compact" if compact else "dash_period_pnl"
    months = period_radio(key=key, default="1년")
    grain = st.radio(
        "보기",
        ["일자별", "월별"],
        horizontal=True,
        key="realized_pnl_grain",
        help="일자별: 거래·배당 기록을 날짜 단위로 봅니다.",
    )

    tickers = _ticker_options(df_all)
    selected_ticker: str | None = None
    if not compact:
        c1, c2 = st.columns([1.2, 1], gap="small")
        with c1:
            scope = st.radio("범위", ["전체", "종목"], horizontal=True, key="realized_pnl_scope")
        with c2:
            if scope == "종목":
                if not tickers:
                    st.warning("종목별 실현 기록이 없습니다.")
                    return
                selected_ticker = st.selectbox("종목", tickers, key="realized_pnl_ticker")
            else:
                st.write("")
        if scope == "종목":
            scoped = df_all[
                (df_all["asset_ref"] == selected_ticker)
                & (df_all["pnl_kind"].isin(["trade_realized", "dividend"]))
            ].copy()
        else:
            scoped = df_all
    else:
        scoped = df_all

    df = filter_by_period(scoped, months)
    if df.empty:
        st.info("선택한 기간에 실현손익이 없습니다.")
        return

    _kpi_row(df, value_col, unit, use_krw=use_krw)

    export = df.dropna(subset=["event_date"]).copy()
    if not export.empty:
        export_disp = pd.DataFrame(
            {
                "일자": export["event_date"].dt.strftime("%Y-%m-%d"),
                "구분": export["pnl_kind_ko"],
                "종목": export["asset_name"],
                "티커": export["asset_ref"],
                "손익": export[value_col],
                "통화": export["currency"],
            }
        )
        download_csv_button(
            export_disp, filename_prefix="realized_pnl", key="export_pnl_csv"
        )

    if grain == "일자별":
        _chart_daily(df, value_col, unit, height=280 if not compact else 240)
        if not compact:
            _table_daily_ledger(df, value_col, use_krw=use_krw)
    else:
        _chart_monthly_by_kind(df, value_col, unit, height=280 if not compact else 240)
        if selected_ticker:
            by_kind = (
                df.groupby("pnl_kind_ko", as_index=False)[value_col]
                .sum()
                .rename(columns={"pnl_kind_ko": "구분", value_col: "합계"})
                .sort_values("합계", ascending=False)
            )
            disp = by_kind.copy()
            disp["합계"] = disp["합계"].map(lambda v: _fmt(float(v), use_krw=use_krw))
            st.dataframe(disp, use_container_width=True, hide_index=True)
        elif not compact:
            _table_by_ticker(df, value_col, use_krw=use_krw)
