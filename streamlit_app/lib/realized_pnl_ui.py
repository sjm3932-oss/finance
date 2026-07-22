"""Combined realized P&L charts (trades + dividends + interest)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib.theme import CHART_COLORS, PRIMARY, chart_layout, show_plotly
from lib.ui_ko import PNL_KIND_KO


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


def load_total_realized(client) -> pd.DataFrame:
    rows = (
        client.table("v_total_realized_pnl")
        .select("event_date,pnl_kind,asset_ref,pnl,currency")
        .order("event_date")
        .execute()
        .data
        or []
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce").fillna(0.0)
    df["currency"] = df["currency"].fillna("KRW").astype(str).str.upper()
    df["pnl_kind_ko"] = df["pnl_kind"].map(lambda x: PNL_KIND_KO.get(x, x))
    rate = _usdkrw(client) or 0.0
    df["pnl_krw"] = df.apply(
        lambda r: float(r["pnl"]) * rate if r["currency"] == "USD" and rate else float(r["pnl"]),
        axis=1,
    )
    # If USD and no rate, keep USD column visible but pnl_krw as NaN for those rows
    if rate <= 0:
        df.loc[df["currency"] == "USD", "pnl_krw"] = pd.NA
    return df


def render_total_realized_pnl(client, *, compact: bool = False) -> None:
    """Charts: cumulative realized P&L + breakdown by kind (매매·배당·이자)."""
    df = load_total_realized(client)
    if df.empty:
        st.info(
            "실현손익 데이터가 없습니다. 매도·배당·이자(현금수입/부채이자)가 쌓이면 여기에 합산됩니다."
        )
        return

    rate = _usdkrw(client)
    use_krw = df["pnl_krw"].notna().any()
    value_col = "pnl_krw" if use_krw else "pnl"
    unit = "원" if use_krw else "표시통화"
    total = float(df[value_col].sum(skipna=True) or 0)

    by_kind = (
        df.groupby("pnl_kind_ko", as_index=False)[value_col]
        .sum()
        .rename(columns={value_col: "합계"})
        .sort_values("합계", ascending=False)
    )

    # KPI row
    cols = st.columns(min(5, max(2, len(by_kind) + 1)))
    cols[0].metric(f"실현손익 합계 ({unit})", f"{total:,.0f}" if use_krw else f"{total:,.2f}")
    for i, row in enumerate(by_kind.itertuples(index=False), start=1):
        if i >= len(cols):
            break
        cols[i].metric(str(row.pnl_kind_ko), f"{float(row.합계):,.0f}" if use_krw else f"{float(row.합계):,.2f}")
    if use_krw and rate:
        st.caption(f"달러 항목은 현재 환율 {rate:,.2f}원으로 환산했습니다.")
    elif (df["currency"] == "USD").any() and not use_krw:
        st.caption("환율(USDKRW)이 없어 통화별 단순합으로 표시합니다. 대시보드에서 시세를 갱신하세요.")

    # Cumulative line
    daily = (
        df.dropna(subset=["event_date"])
        .groupby("event_date", as_index=False)[value_col]
        .sum()
        .sort_values("event_date")
    )
    daily["누적실현손익"] = daily[value_col].cumsum()

    if compact:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=daily["event_date"],
                y=daily["누적실현손익"],
                mode="lines+markers",
                name="누적 실현손익",
                line=dict(color=PRIMARY, width=3),
                fill="tozeroy",
                fillcolor="rgba(3,199,90,0.12)",
            )
        )
        fig.update_layout(
            **chart_layout(280, with_title=True),
            title="누적 실현손익 (매매·배당·이자 합산)",
            yaxis_title=unit,
            xaxis_title="일자",
        )
        show_plotly(fig)
        return

    left, right = st.columns(2, gap="medium")
    with left:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=daily["event_date"],
                y=daily["누적실현손익"],
                mode="lines+markers",
                name="누적 실현손익",
                line=dict(color=PRIMARY, width=3),
                fill="tozeroy",
                fillcolor="rgba(3,199,90,0.12)",
            )
        )
        fig.update_layout(
            **chart_layout(320, with_title=True),
            title="누적 실현손익",
            yaxis_title=unit,
            xaxis_title="일자",
        )
        show_plotly(fig)

    with right:
        if not by_kind.empty:
            fig = px.pie(
                by_kind,
                names="pnl_kind_ko",
                values="합계",
                color_discrete_sequence=CHART_COLORS,
                hole=0.45,
            )
            fig.update_layout(**chart_layout(320, with_title=True), title="실현손익 구성")
            show_plotly(fig)

    # Monthly stacked by kind
    tmp = df.dropna(subset=["event_date"]).copy()
    if not tmp.empty:
        tmp["월"] = tmp["event_date"].dt.to_period("M").astype(str)
        monthly = (
            tmp.groupby(["월", "pnl_kind_ko"], as_index=False)[value_col]
            .sum()
            .rename(columns={value_col: "손익"})
        )
        fig = px.bar(
            monthly,
            x="월",
            y="손익",
            color="pnl_kind_ko",
            color_discrete_sequence=CHART_COLORS,
            barmode="relative",
            labels={"pnl_kind_ko": "구분", "손익": f"손익({unit})"},
        )
        fig.update_layout(
            **chart_layout(320, with_title=True),
            title="월별 실현손익 (매매·배당·이자)",
            legend_title_text="",
        )
        show_plotly(fig)

    # Waterfall-ish contribution by kind (horizontal bar)
    if not by_kind.empty:
        fig = go.Figure(
            go.Bar(
                x=by_kind["합계"],
                y=by_kind["pnl_kind_ko"],
                orientation="h",
                marker_color=[PRIMARY if v >= 0 else "#FF6B6B" for v in by_kind["합계"]],
                text=[f"{v:,.0f}" if use_krw else f"{v:,.2f}" for v in by_kind["합계"]],
                textposition="auto",
            )
        )
        fig.update_layout(
            **chart_layout(max(240, 56 * len(by_kind) + 80), with_title=True),
            title="항목별 실현손익 기여",
            xaxis_title=unit,
        )
        show_plotly(fig)
