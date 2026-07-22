"""Dashboard hub: overview / holdings / asset-flow charts / entry forms."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.asset_flows_ui import render_flow_charts, render_flow_forms  # noqa: E402
from lib.auth import ensure_profile, require_auth  # noqa: E402
from lib.market_data import STALE_HOURS, fetch_usdkrw, is_stale, refresh_tickers  # noqa: E402
from lib.realized_pnl_ui import render_total_realized_pnl  # noqa: E402
from lib.supabase_client import get_service_client  # noqa: E402
from lib.theme import (  # noqa: E402
    CHART_COLORS,
    PRIMARY,
    apply_theme,
    chart_layout,
    page_hero,
    render_subnav,
    show_plotly,
)

st.set_page_config(page_title="대시보드", page_icon="💚", layout="wide")
apply_theme(max_width=1120)

VIEWS = ["한눈에", "종목", "실현손익", "자산 흐름", "기록하기"]


def _fmt_money(v, currency="KRW") -> str:
    if v is None:
        return "—"
    try:
        n = float(v)
    except (TypeError, ValueError):
        return "—"
    if currency == "USD":
        return f"${n:,.2f}"
    return f"₩{n:,.0f}"


def _svc_fallback(client):
    try:
        return get_service_client()
    except Exception:
        return client


def _run_snapshot(client):
    try:
        return client.rpc("compute_daily_snapshot").execute().data
    except Exception:
        return _svc_fallback(client).rpc("compute_daily_snapshot").execute().data


def _load_holding_snaps(client, days: int = 90) -> pd.DataFrame:
    since = (date.today() - timedelta(days=days)).isoformat()
    rows = (
        client.table("holding_daily_snapshots")
        .select(
            "snapshot_date,account_id,ticker,name,quantity,avg_price,price,"
            "currency,market_value,market_value_krw,return_rate,usdkrw"
        )
        .gte("snapshot_date", since)
        .order("snapshot_date")
        .execute()
        .data
        or []
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"]).dt.date
    for col in ("quantity", "avg_price", "price", "market_value", "market_value_krw", "return_rate", "usdkrw"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _load_daily_totals(client, days: int = 90) -> pd.DataFrame:
    since = (date.today() - timedelta(days=days)).isoformat()
    rows = (
        client.table("daily_snapshots")
        .select("*")
        .gte("snapshot_date", since)
        .order("snapshot_date")
        .execute()
        .data
        or []
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"]).dt.date
    for col in ("net_assets", "total_investment", "total_debt", "cash_ratio"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _live_holdings(client, holdings: list[dict]) -> tuple[list[dict], float, float, float, bool]:
    prices = {
        p["ticker"]: p
        for p in (client.table("market_prices").select("*").execute().data or [])
    }
    usdkrw_row = prices.get("USDKRW")
    usdkrw = float(usdkrw_row["price"]) if usdkrw_row else None

    total_usd = 0.0
    total_krw = 0.0
    live_rows: list[dict] = []
    any_stale = False
    for h in holdings:
        mp = prices.get(h["ticker"])
        stale = is_stale(mp.get("updated_at") if mp else None)
        any_stale = any_stale or stale
        price = mp.get("price") if mp else None
        qty = float(h.get("quantity") or 0)
        avg = float(h.get("avg_price") or 0)
        cur = h.get("currency") or (mp.get("currency") if mp else None) or "USD"
        mv = float(price) * qty if price is not None else None
        if mv is not None:
            if cur == "USD":
                total_usd += mv
                if usdkrw:
                    total_krw += mv * usdkrw
            else:
                total_krw += mv
                if usdkrw:
                    total_usd += mv / usdkrw
        ret = ((float(price) - avg) / avg * 100) if price is not None and avg else None
        live_rows.append(
            {
                "ticker": h["ticker"],
                "name": h.get("name"),
                "qty": qty,
                "avg": avg,
                "price": price,
                "return_%": ret,
                "value": mv,
                "ccy": cur,
                "시세": "지연" if stale else ("없음" if price is None else "정상"),
            }
        )

    debts = client.table("debts").select("principal").execute().data or []
    total_debt = sum(float(d.get("principal") or 0) for d in debts)
    return live_rows, total_usd, total_krw, total_debt, any_stale


def _toolbar(client, tickers: list[str]) -> None:
    c1, c2, c3 = st.columns([1, 1, 1.2], gap="small")
    with c1:
        if st.button("시세 새로고침", type="primary", key="dash_refresh_px"):
            with st.spinner("시세·환율 조회 중…"):
                rows, errors = refresh_tickers(tickers)
                writer = client
                try:
                    if rows:
                        writer.table("market_prices").upsert(rows, on_conflict="ticker").execute()
                except Exception:
                    writer = _svc_fallback(client)
                    if rows:
                        writer.table("market_prices").upsert(rows, on_conflict="ticker").execute()
                try:
                    usdkrw = fetch_usdkrw()
                    writer.table("market_prices").upsert(
                        {"ticker": "USDKRW", "price": usdkrw, "currency": "KRW"},
                        on_conflict="ticker",
                    ).execute()
                    writer.table("market_index_snapshots").upsert(
                        {"snapshot_date": date.today().isoformat(), "usdkrw": usdkrw},
                        on_conflict="snapshot_date",
                    ).execute()
                    st.success(f"시세 {len(rows)}종 · 달러원환율 {usdkrw:,.2f}")
                except Exception as exc:
                    st.warning(f"환율 실패: {exc}")
                for e in errors:
                    st.caption(f"⚠ {e}")
            st.rerun()
    with c2:
        if st.button("오늘 스냅샷", key="dash_snap"):
            with st.spinner("일별 스냅샷 기록…"):
                snap = _run_snapshot(client)
            st.success(snap)
            st.rerun()
    with c3:
        st.caption(f"시세 {STALE_HOURS:.0f}시간 초과 시 「시세 지연」")


def view_overview(client, live_rows, total_usd, total_krw, total_debt, any_stale) -> None:
    net_krw = (total_krw - total_debt) if total_krw else None
    m1, m2, m3, m4 = st.columns(4, gap="small")
    m1.metric("투자자산 (달러)", _fmt_money(total_usd, "USD") if total_usd else "—")
    m2.metric("투자자산 (원)", _fmt_money(total_krw, "KRW") if total_krw else "—")
    m3.metric("부채", _fmt_money(total_debt, "KRW"))
    m4.metric("순자산(추정)", _fmt_money(net_krw, "KRW") if net_krw is not None else "—")
    if any_stale:
        st.warning("일부 시세가 지연되었습니다.")

    st.markdown("##### 실현손익 (매매·배당·이자 합산)")
    render_total_realized_pnl(client, compact=True)

    tdf = _load_daily_totals(client)
    hdf = _load_holding_snaps(client)

    left, right = st.columns(2, gap="medium")
    with left:
        st.markdown("##### 총자산 추이")
        if tdf.empty:
            st.info("스냅샷이 없습니다. 「오늘 스냅샷」을 눌러 시작하세요.")
        else:
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=tdf["snapshot_date"],
                    y=tdf["total_investment"],
                    name="투자자산",
                    mode="lines+markers",
                    line=dict(color=PRIMARY, width=3),
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=tdf["snapshot_date"],
                    y=tdf["net_assets"],
                    name="순자산",
                    mode="lines+markers",
                    line=dict(color="#019C46", width=2.5),
                )
            )
            if "total_debt" in tdf.columns:
                fig.add_trace(
                    go.Scatter(
                        x=tdf["snapshot_date"],
                        y=tdf["total_debt"],
                        name="부채",
                        mode="lines+markers",
                        line=dict(color="#94A3B8", width=2, dash="dot"),
                    )
                )
            fig.update_layout(**chart_layout(300), yaxis_title="원", xaxis_title="날짜")
            show_plotly(fig)

    with right:
        st.markdown("##### 현재 구성")
        pie_src = [r for r in live_rows if r.get("value") is not None]
        if not pie_src and not hdf.empty:
            latest = hdf["snapshot_date"].max()
            day = hdf[hdf["snapshot_date"] == latest].dropna(subset=["market_value_krw"])
            if not day.empty:
                fig = px.pie(
                    day,
                    names="ticker",
                    values="market_value_krw",
                    color_discrete_sequence=CHART_COLORS,
                    hole=0.45,
                )
                fig.update_layout(**chart_layout(300, with_title=True), title=str(latest))
                show_plotly(fig)
            else:
                st.info("구성 차트를 그릴 데이터가 없습니다.")
        elif pie_src:
            pdf = pd.DataFrame(pie_src)
            fig = px.pie(
                pdf,
                names="ticker",
                values="value",
                color_discrete_sequence=CHART_COLORS,
                hole=0.45,
            )
            fig.update_layout(**chart_layout(300, with_title=True), title="실시간 평가")
            show_plotly(fig)
        else:
            st.info("보유 종목이 없습니다.")

    # Compact return bars instead of a big table
    if live_rows:
        st.markdown("##### 종목 수익률")
        rdf = pd.DataFrame(live_rows).dropna(subset=["return_%"])
        if not rdf.empty:
            rdf = rdf.sort_values("return_%")
            fig = go.Figure(
                go.Bar(
                    x=rdf["return_%"],
                    y=rdf["ticker"],
                    orientation="h",
                    marker_color=[PRIMARY if v >= 0 else "#FF6B6B" for v in rdf["return_%"]],
                    text=[f"{v:.1f}%" for v in rdf["return_%"]],
                    textposition="auto",
                )
            )
            fig.update_layout(**chart_layout(max(220, 28 * len(rdf) + 80)), xaxis_title="수익률(%)")
            show_plotly(fig)


def view_tickers(client, live_rows) -> None:
    hdf = _load_holding_snaps(client)
    tickers = sorted({r["ticker"] for r in live_rows}) or (
        sorted(hdf["ticker"].unique().tolist()) if not hdf.empty else []
    )
    if not tickers:
        st.info("표시할 종목이 없습니다.")
        return

    pick = st.selectbox("종목 선택", options=tickers)
    row = next((r for r in live_rows if r["ticker"] == pick), None)
    if row:
        a, b, c, d = st.columns(4, gap="small")
        a.metric("수량", f"{float(row['qty']):,.4f}".rstrip("0").rstrip("."))
        b.metric("현재가", _fmt_money(row["price"], row.get("ccy") or "USD"))
        c.metric("평가액", _fmt_money(row["value"], row.get("ccy") or "USD"))
        d.metric("수익률", f"{row['return_%']:.2f}%" if row.get("return_%") is not None else "—")

    one = hdf[hdf["ticker"] == pick].sort_values("snapshot_date") if not hdf.empty else pd.DataFrame()
    if one.empty:
        st.info("이 종목의 일별 스냅샷이 아직 없습니다.")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=one["snapshot_date"],
            y=one["market_value_krw"],
            name="평가액(원)",
            mode="lines+markers",
            line=dict(color=PRIMARY, width=3),
            yaxis="y1",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=one["snapshot_date"],
            y=one["price"],
            name="가격",
            mode="lines+markers",
            line=dict(color="#00A3FF", width=2),
            yaxis="y2",
        )
    )
    fig.update_layout(
        **chart_layout(320, with_title=True),
        title=f"{pick} 일별 추이",
        yaxis=dict(title="평가액(원)"),
        yaxis2=dict(title="가격", overlaying="y", side="right"),
    )
    show_plotly(fig)

    plot_df = hdf.dropna(subset=["market_value_krw"])
    if not plot_df.empty:
        st.markdown("##### 종목별 평가액 비교")
        fig2 = px.line(
            plot_df,
            x="snapshot_date",
            y="market_value_krw",
            color="ticker",
            markers=True,
            color_discrete_sequence=CHART_COLORS,
            labels={"snapshot_date": "날짜", "market_value_krw": "평가액(원)", "ticker": "종목"},
        )
        fig2.update_layout(**chart_layout(300))
        show_plotly(fig2)


def main() -> None:
    page_hero("대시보드", "한눈에 · 종목 · 실현손익 · 자산 흐름 · 기록하기")
    view = render_subnav(VIEWS, state_key="dash_view", default="한눈에")

    user, client = require_auth()
    ensure_profile(user, client)

    holdings = client.table("holdings").select("*").execute().data or []
    tickers = sorted({h["ticker"] for h in holdings})
    live_rows, total_usd, total_krw, total_debt, any_stale = _live_holdings(client, holdings)

    if view in ("한눈에", "종목"):
        _toolbar(client, tickers)

    if view == "한눈에":
        view_overview(client, live_rows, total_usd, total_krw, total_debt, any_stale)
    elif view == "종목":
        view_tickers(client, live_rows)
    elif view == "실현손익":
        st.caption("매매 실현 · 배당 · 이자수입 · 이자비용을 모두 합산한 실현손익입니다.")
        render_total_realized_pnl(client, compact=False)
    elif view == "자산 흐름":
        render_flow_charts(client)
    else:
        render_flow_forms(client, user)


main()
