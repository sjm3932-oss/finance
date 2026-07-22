"""Page: Portfolio dashboard with daily holding snapshots + charts."""

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

from lib.auth import ensure_profile, require_auth  # noqa: E402
from lib.market_data import STALE_HOURS, fetch_usdkrw, is_stale, refresh_tickers  # noqa: E402
from lib.supabase_client import get_service_client  # noqa: E402

st.set_page_config(page_title="Dashboard", layout="wide")

st.markdown(
    """
<style>
  .block-container { padding-top: 1rem; max-width: 1100px; }
  div.stButton > button { width: 100%; min-height: 2.8rem; }
</style>
""",
    unsafe_allow_html=True,
)

CHART_LAYOUT = dict(
    margin=dict(l=8, r=8, t=40, b=8),
    height=320,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    hovermode="x unified",
)


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


def main() -> None:
    st.title("Dashboard")
    st.caption("일별 자산 스냅샷 · 총자산/종목별 추이 · 특정일·특정종목 상세")

    user, client = require_auth()
    ensure_profile(user, client)

    holdings = client.table("holdings").select("*").execute().data or []
    tickers = sorted({h["ticker"] for h in holdings})

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("시세 새로고침", type="primary"):
            with st.spinner("Yahoo / Frankfurter…"):
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
                    st.success(f"시세 {len(rows)}종 · USD/KRW {usdkrw:,.2f}")
                except Exception as exc:
                    st.warning(f"환율 실패: {exc}")
                for e in errors:
                    st.caption(f"⚠ {e}")
            st.rerun()
    with c2:
        if st.button("오늘 스냅샷 저장"):
            with st.spinner("일별 스냅샷 기록…"):
                snap = _run_snapshot(client)
            st.success(snap)
            st.rerun()
    with c3:
        st.caption(f"시세 {STALE_HOURS:.0f}h 초과 시 「시세 지연」")

    # Live metrics
    prices = {
        p["ticker"]: p
        for p in (client.table("market_prices").select("*").execute().data or [])
    }
    usdkrw_row = prices.get("USDKRW")
    usdkrw = float(usdkrw_row["price"]) if usdkrw_row else None

    total_usd = 0.0
    total_krw = 0.0
    live_rows = []
    any_stale = False
    for h in holdings:
        mp = prices.get(h["ticker"])
        stale = is_stale(mp.get("updated_at") if mp else None)
        any_stale = any_stale or stale
        price = mp.get("price") if mp else None
        qty = float(h.get("quantity") or 0)
        avg = float(h.get("avg_price") or 0)
        cur = (h.get("currency") or (mp.get("currency") if mp else None) or "USD")
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
                "시세": "지연" if stale else ("없음" if price is None else "OK"),
            }
        )

    debts = client.table("debts").select("principal").execute().data or []
    total_debt = sum(float(d.get("principal") or 0) for d in debts)
    net_krw = (total_krw - total_debt) if total_krw else None

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("투자자산 (USD)", _fmt_money(total_usd, "USD") if total_usd else "—")
    m2.metric("투자자산 (KRW)", _fmt_money(total_krw, "KRW") if total_krw else "—")
    m3.metric("부채", _fmt_money(total_debt, "KRW"))
    m4.metric("순자산(추정)", _fmt_money(net_krw, "KRW") if net_krw is not None else "—")
    if any_stale:
        st.warning("일부 시세가 지연되었습니다.")

    # Historical data
    hdf = _load_holding_snaps(client)
    tdf = _load_daily_totals(client)

    st.subheader("총자산 추이")
    if tdf.empty:
        st.info("스냅샷이 없습니다. 「오늘 스냅샷 저장」을 눌러 시작하세요.")
    else:
        fig_total = go.Figure()
        fig_total.add_trace(
            go.Scatter(
                x=tdf["snapshot_date"],
                y=tdf["total_investment"],
                name="투자자산",
                mode="lines+markers",
            )
        )
        fig_total.add_trace(
            go.Scatter(
                x=tdf["snapshot_date"],
                y=tdf["net_assets"],
                name="순자산",
                mode="lines+markers",
            )
        )
        if "total_debt" in tdf.columns:
            fig_total.add_trace(
                go.Scatter(
                    x=tdf["snapshot_date"],
                    y=tdf["total_debt"],
                    name="부채",
                    mode="lines+markers",
                )
            )
        fig_total.update_layout(**CHART_LAYOUT, yaxis_title="KRW", xaxis_title="날짜")
        fig_total.update_layout(autosize=True)
        st.plotly_chart(fig_total, use_container_width=True, config={"responsive": True})

    st.subheader("종목별 평가액 추이 (KRW)")
    if hdf.empty:
        st.info("종목 스냅샷이 아직 없습니다.")
    else:
        plot_df = hdf.dropna(subset=["market_value_krw"]).copy()
        if plot_df.empty:
            st.info("평가액이 있는 스냅샷이 없습니다 (시세 없는 종목 등).")
        else:
            fig_assets = px.line(
                plot_df,
                x="snapshot_date",
                y="market_value_krw",
                color="ticker",
                markers=True,
                labels={
                    "snapshot_date": "날짜",
                    "market_value_krw": "평가액 (KRW)",
                    "ticker": "종목",
                },
            )
            fig_assets.update_layout(**CHART_LAYOUT)
            st.plotly_chart(fig_assets, use_container_width=True, config={"responsive": True})

            # Stacked area composition
            pivot = (
                plot_df.groupby(["snapshot_date", "ticker"], as_index=False)["market_value_krw"]
                .sum()
            )
            fig_stack = px.area(
                pivot,
                x="snapshot_date",
                y="market_value_krw",
                color="ticker",
                labels={
                    "snapshot_date": "날짜",
                    "market_value_krw": "평가액 (KRW)",
                    "ticker": "종목",
                },
            )
            fig_stack.update_layout(**CHART_LAYOUT, title="구성 비중(누적)")
            st.plotly_chart(fig_stack, use_container_width=True, config={"responsive": True})

    st.subheader("특정일 · 특정 자산 상세")
    dates = sorted({r["snapshot_date"] for r in (hdf.to_dict("records") if not hdf.empty else [])})
    if not dates:
        # fall back to live table only
        st.dataframe(live_rows, use_container_width=True, hide_index=True)
        return

    dcol, tcol = st.columns(2)
    with dcol:
        pick_date = st.date_input(
            "조회 날짜",
            value=max(dates),
            min_value=min(dates),
            max_value=max(dates),
        )
    tickers_avail = sorted(hdf["ticker"].unique().tolist())
    with tcol:
        pick_ticker = st.selectbox("종목", options=["(전체)"] + tickers_avail)

    day_df = hdf[hdf["snapshot_date"] == pick_date].copy()
    if pick_ticker != "(전체)":
        day_df = day_df[day_df["ticker"] == pick_ticker]

    if day_df.empty:
        st.warning("해당 날짜/종목 스냅샷이 없습니다.")
    else:
        # Summary metrics for selection
        if pick_ticker == "(전체)":
            day_total = day_df["market_value_krw"].sum(skipna=True)
            st.metric(f"{pick_date} 총 평가액", _fmt_money(day_total, "KRW"))
            # Pie of that day
            pie_df = day_df.dropna(subset=["market_value_krw"])
            if not pie_df.empty:
                fig_pie = px.pie(
                    pie_df,
                    names="ticker",
                    values="market_value_krw",
                    title=f"{pick_date} 자산 구성",
                )
                fig_pie.update_layout(margin=dict(l=8, r=8, t=40, b=8), height=340)
                st.plotly_chart(fig_pie, use_container_width=True, config={"responsive": True})
        else:
            row = day_df.iloc[0]
            a, b, c, d = st.columns(4)
            a.metric("수량", f"{float(row['quantity']):,.4f}".rstrip("0").rstrip("."))
            b.metric("종가/시세", _fmt_money(row["price"], row.get("currency") or "USD"))
            c.metric("평가액(KRW)", _fmt_money(row["market_value_krw"], "KRW"))
            d.metric("수익률", f"{row['return_rate']:.2f}%" if pd.notna(row["return_rate"]) else "—")

            # Single-asset history chart
            one = hdf[hdf["ticker"] == pick_ticker].sort_values("snapshot_date")
            fig_one = go.Figure()
            fig_one.add_trace(
                go.Scatter(
                    x=one["snapshot_date"],
                    y=one["market_value_krw"],
                    name="평가액(KRW)",
                    mode="lines+markers",
                    yaxis="y1",
                )
            )
            fig_one.add_trace(
                go.Scatter(
                    x=one["snapshot_date"],
                    y=one["price"],
                    name="가격",
                    mode="lines+markers",
                    yaxis="y2",
                )
            )
            fig_one.update_layout(
                **CHART_LAYOUT,
                title=f"{pick_ticker} 일별 추이",
                yaxis=dict(title="KRW"),
                yaxis2=dict(title="Price", overlaying="y", side="right"),
            )
            st.plotly_chart(fig_one, use_container_width=True, config={"responsive": True})

        show = day_df[
            [
                "snapshot_date",
                "ticker",
                "name",
                "quantity",
                "avg_price",
                "price",
                "currency",
                "market_value",
                "market_value_krw",
                "return_rate",
                "usdkrw",
            ]
        ]
        st.dataframe(show, use_container_width=True, hide_index=True)

    st.subheader("현재 보유 (실시간)")
    st.dataframe(live_rows, use_container_width=True, hide_index=True)


main()
