"""Combined realized P&L charts (trades + dividends + interest).

Shows overall and per-ticker views, change over time, and kind split
(매매실현 / 배당 / 이자).
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib.theme import CHART_COLORS, PRIMARY, apply_chart_layout, show_plotly
from lib.ui_ko import PNL_KIND_KO

# Stable colors per P&L kind (Korean labels after mapping)
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
    df["asset_ref"] = df["asset_ref"].fillna("기타").astype(str)
    rate = _usdkrw(client) or 0.0
    df["pnl_krw"] = df.apply(
        lambda r: float(r["pnl"]) * rate if r["currency"] == "USD" and rate else float(r["pnl"]),
        axis=1,
    )
    if rate <= 0:
        df.loc[df["currency"] == "USD", "pnl_krw"] = pd.NA
    return df


def _fmt(v: float, *, use_krw: bool) -> str:
    if pd.isna(v):
        return "—"
    return f"{v:,.0f}" if use_krw else f"{v:,.2f}"


def _kind_color_map(labels: list[str] | pd.Series) -> dict[str, str]:
    out: dict[str, str] = {}
    extras = [c for c in CHART_COLORS if c not in KIND_COLORS.values()]
    ei = 0
    for lab in labels:
        if lab in KIND_COLORS:
            out[lab] = KIND_COLORS[lab]
        else:
            out[lab] = extras[ei % len(extras)] if extras else PRIMARY
            ei += 1
    return out


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
    # Prefer fixed order: 매매 / 배당 first
    kind_labels = [k for k in KIND_ORDER if k in by_kind.index] + [
        k for k in by_kind.index if k not in KIND_ORDER
    ]
    cols = st.columns(min(5, max(2, len(kind_labels) + 1)))
    cols[0].metric(f"실현손익 합계 ({unit})", _fmt(total, use_krw=use_krw))
    for i, kind in enumerate(kind_labels, start=1):
        if i >= len(cols):
            break
        cols[i].metric(kind, _fmt(float(by_kind[kind]), use_krw=use_krw))


def _ticker_options(df: pd.DataFrame) -> list[str]:
    """Tickers that appear in trade or dividend rows (종목별)."""
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


def _chart_cumulative_total(daily: pd.DataFrame, value_col: str, unit: str, *, height: int) -> None:
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
    apply_chart_layout(
        fig,
        height,
        title="누적 실현손익",
        yaxis_title=unit,
        xaxis_title="일자",
    )
    show_plotly(fig)


def _chart_period_change(daily: pd.DataFrame, value_col: str, unit: str, *, height: int) -> None:
    """Bar chart of period-over-period realized P&L change (증감)."""
    colors = [PRIMARY if v >= 0 else "#FF6B6B" for v in daily[value_col]]
    fig = go.Figure(
        go.Bar(
            x=daily["event_date"],
            y=daily[value_col],
            marker_color=colors,
            name="기간 증감",
            text=[f"{v:+,.0f}" if abs(v) >= 1 else f"{v:+,.2f}" for v in daily[value_col]],
            textposition="outside",
            cliponaxis=False,
        )
    )
    apply_chart_layout(
        fig,
        height,
        title="실현손익 증감 (일자별)",
        yaxis_title=unit,
        xaxis_title="일자",
        showlegend=False,
    )
    show_plotly(fig)


def _chart_cumulative_by_kind(df: pd.DataFrame, value_col: str, unit: str, *, height: int) -> None:
    """Multi-line cumulative P&L by kind (매매 vs 배당 vs …)."""
    tmp = df.dropna(subset=["event_date"]).copy()
    if tmp.empty:
        return
    daily_kind = (
        tmp.groupby(["event_date", "pnl_kind_ko"], as_index=False)[value_col]
        .sum()
        .sort_values("event_date")
    )
    # Pivot so each kind has a continuous series, then cumsum
    pivot = (
        daily_kind.pivot(index="event_date", columns="pnl_kind_ko", values=value_col)
        .fillna(0.0)
        .sort_index()
    )
    cum = pivot.cumsum()
    kinds = [k for k in KIND_ORDER if k in cum.columns] + [
        k for k in cum.columns if k not in KIND_ORDER
    ]
    cmap = _kind_color_map(kinds)
    fig = go.Figure()
    for kind in kinds:
        fig.add_trace(
            go.Scatter(
                x=cum.index,
                y=cum[kind],
                mode="lines",
                name=kind,
                line=dict(color=cmap[kind], width=2.5),
            )
        )
    apply_chart_layout(
        fig,
        height,
        title="종류별 누적 실현손익 (매매 · 배당 · 이자)",
        yaxis_title=unit,
        xaxis_title="일자",
        legend_title_text="",
    )
    show_plotly(fig)


def _chart_monthly_by_kind(df: pd.DataFrame, value_col: str, unit: str, *, height: int) -> None:
    tmp = df.dropna(subset=["event_date"]).copy()
    if tmp.empty:
        return
    tmp["월"] = tmp["event_date"].dt.to_period("M").astype(str)
    monthly = (
        tmp.groupby(["월", "pnl_kind_ko"], as_index=False)[value_col]
        .sum()
        .rename(columns={value_col: "손익"})
    )
    kinds = [k for k in KIND_ORDER if k in set(monthly["pnl_kind_ko"])] + [
        k for k in monthly["pnl_kind_ko"].unique() if k not in KIND_ORDER
    ]
    cmap = _kind_color_map(kinds)
    fig = px.bar(
        monthly,
        x="월",
        y="손익",
        color="pnl_kind_ko",
        color_discrete_map=cmap,
        category_orders={"pnl_kind_ko": kinds},
        barmode="relative",
        labels={"pnl_kind_ko": "구분", "손익": f"손익({unit})"},
    )
    apply_chart_layout(
        fig,
        height,
        title="월별 실현손익 (매매 · 배당 · 이자)",
        legend_title_text="",
    )
    show_plotly(fig)


def _chart_by_ticker(df: pd.DataFrame, value_col: str, unit: str, *, use_krw: bool, height: int) -> None:
    """Horizontal bars: total realized P&L per ticker (trade + dividend)."""
    mask = df["pnl_kind"].isin(["trade_realized", "dividend"])
    sub = df.loc[mask].copy()
    if sub.empty:
        st.info("종목별 실현손익(매매·배당) 데이터가 없습니다.")
        return
    by_t = (
        sub.groupby("asset_ref", as_index=False)[value_col]
        .sum()
        .rename(columns={value_col: "합계"})
        .sort_values("합계")
    )
    fig = go.Figure(
        go.Bar(
            x=by_t["합계"],
            y=by_t["asset_ref"],
            orientation="h",
            marker_color=[PRIMARY if v >= 0 else "#FF6B6B" for v in by_t["합계"]],
            text=[_fmt(v, use_krw=use_krw) for v in by_t["합계"]],
            textposition="auto",
            name="종목 합계",
        )
    )
    apply_chart_layout(
        fig,
        max(height, 48 * len(by_t) + 100),
        title="종목별 실현손익 합계",
        xaxis_title=unit,
        yaxis_title="",
        showlegend=False,
    )
    show_plotly(fig)


def _chart_ticker_by_kind(df: pd.DataFrame, value_col: str, unit: str, *, height: int) -> None:
    """Stacked bar: each ticker split into 매매실현 / 배당."""
    mask = df["pnl_kind"].isin(["trade_realized", "dividend"])
    sub = df.loc[mask].copy()
    if sub.empty:
        return
    g = (
        sub.groupby(["asset_ref", "pnl_kind_ko"], as_index=False)[value_col]
        .sum()
        .rename(columns={value_col: "손익"})
    )
    kinds = [k for k in ("매매실현", "배당") if k in set(g["pnl_kind_ko"])]
    if not kinds:
        return
    cmap = _kind_color_map(kinds)
    # Order tickers by total
    order = (
        g.groupby("asset_ref")["손익"].sum().sort_values(ascending=False).index.tolist()
    )
    fig = px.bar(
        g,
        x="asset_ref",
        y="손익",
        color="pnl_kind_ko",
        color_discrete_map=cmap,
        category_orders={"asset_ref": order, "pnl_kind_ko": kinds},
        barmode="group",
        labels={"asset_ref": "종목", "pnl_kind_ko": "구분", "손익": f"손익({unit})"},
    )
    apply_chart_layout(
        fig,
        height,
        title="종목별 · 종류별 실현손익 (매매 vs 배당)",
        legend_title_text="",
        xaxis_title="종목",
    )
    show_plotly(fig)


def _table_by_ticker(df: pd.DataFrame, value_col: str, *, use_krw: bool) -> None:
    mask = df["pnl_kind"].isin(["trade_realized", "dividend"])
    sub = df.loc[mask].copy()
    if sub.empty:
        return
    pivot = (
        sub.pivot_table(
            index="asset_ref",
            columns="pnl_kind_ko",
            values=value_col,
            aggfunc="sum",
            fill_value=0.0,
        )
        .reindex(columns=[c for c in ("매매실현", "배당") if c in sub["pnl_kind_ko"].unique()], fill_value=0.0)
    )
    pivot["합계"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("합계", ascending=False).reset_index().rename(columns={"asset_ref": "종목"})
    # Format for display
    disp = pivot.copy()
    for c in disp.columns:
        if c == "종목":
            continue
        disp[c] = disp[c].map(lambda v: _fmt(float(v), use_krw=use_krw))
    st.markdown("##### 종목별 상세")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def render_total_realized_pnl(client, *, compact: bool = False) -> None:
    """Charts: overall + per-ticker, change over time, kind split (매매·배당·이자)."""
    df_all = load_total_realized(client)
    if df_all.empty:
        st.info(
            "실현손익 데이터가 없습니다. 매도·배당·이자(현금수입/부채이자)가 쌓이면 여기에 합산됩니다."
        )
        return

    value_col, unit, use_krw, rate = _value_setup(df_all, client)

    if use_krw and rate:
        st.caption(f"달러 항목은 현재 환율 {rate:,.2f}원으로 환산했습니다.")
    elif (df_all["currency"] == "USD").any() and not use_krw:
        st.caption("환율(USDKRW)이 없어 통화별 단순합으로 표시합니다. 대시보드에서 시세를 갱신하세요.")

    # —— compact (overview / asset flows): summary only ——
    if compact:
        _kpi_row(df_all, value_col, unit, use_krw=use_krw)
        daily = (
            df_all.dropna(subset=["event_date"])
            .groupby("event_date", as_index=False)[value_col]
            .sum()
            .sort_values("event_date")
        )
        daily["누적실현손익"] = daily[value_col].cumsum()
        left, right = st.columns(2, gap="medium")
        with left:
            _chart_cumulative_total(daily, value_col, unit, height=280)
        with right:
            _chart_period_change(daily, value_col, unit, height=280)
        return

    # —— full view: 전체 / 종목 ——
    tickers = _ticker_options(df_all)
    scope = st.radio(
        "보기",
        options=["전체", "종목"],
        horizontal=True,
        key="realized_pnl_scope",
        help="전체 합산 또는 특정 종목의 매매·배당 실현손익",
    )

    selected_ticker: str | None = None
    if scope == "종목":
        if not tickers:
            st.warning("종목별 실현손익(매매·배당) 기록이 아직 없습니다.")
            return
        selected_ticker = st.selectbox("종목", tickers, key="realized_pnl_ticker")
        df = df_all[
            (df_all["asset_ref"] == selected_ticker)
            & (df_all["pnl_kind"].isin(["trade_realized", "dividend"]))
        ].copy()
        if df.empty:
            st.info(f"{selected_ticker} 실현손익 데이터가 없습니다.")
            return
        st.caption(f"**{selected_ticker}** — 매매실현과 배당만 표시합니다.")
    else:
        df = df_all

    _kpi_row(df, value_col, unit, use_krw=use_krw)

    daily = (
        df.dropna(subset=["event_date"])
        .groupby("event_date", as_index=False)[value_col]
        .sum()
        .sort_values("event_date")
    )
    daily["누적실현손익"] = daily[value_col].cumsum()

    st.markdown("##### 증감 · 누적")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        _chart_cumulative_total(daily, value_col, unit, height=320)
    with c2:
        _chart_period_change(daily, value_col, unit, height=320)

    st.markdown("##### 종류 구분 (매매 · 배당 · 이자)")
    _chart_cumulative_by_kind(df, value_col, unit, height=320)
    _chart_monthly_by_kind(df, value_col, unit, height=320)

    if scope == "전체":
        st.markdown("##### 종목별")
        t1, t2 = st.columns(2, gap="medium")
        with t1:
            _chart_by_ticker(df, value_col, unit, use_krw=use_krw, height=320)
        with t2:
            _chart_ticker_by_kind(df, value_col, unit, height=320)
        _table_by_ticker(df, value_col, use_krw=use_krw)
    else:
        # Single ticker: kind contribution bars
        by_kind = (
            df.groupby("pnl_kind_ko", as_index=False)[value_col]
            .sum()
            .rename(columns={value_col: "합계"})
        )
        kinds = [k for k in KIND_ORDER if k in set(by_kind["pnl_kind_ko"])]
        cmap = _kind_color_map(kinds)
        fig = go.Figure(
            go.Bar(
                x=by_kind["pnl_kind_ko"],
                y=by_kind["합계"],
                marker_color=[cmap.get(k, PRIMARY) for k in by_kind["pnl_kind_ko"]],
                text=[_fmt(v, use_krw=use_krw) for v in by_kind["합계"]],
                textposition="auto",
            )
        )
        apply_chart_layout(
            fig,
            280,
            title=f"{selected_ticker} · 종류별 실현손익",
            yaxis_title=unit,
            xaxis_title="",
            showlegend=False,
        )
        show_plotly(fig)
