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


def _account_map(client) -> dict[str, str]:
    rows = client.table("accounts").select("id,institution").execute().data or []
    return {str(a["id"]): a.get("institution") or "계좌" for a in rows}


def _live_holdings(client, holdings: list[dict]) -> tuple[list[dict], float, float, float, bool]:
    prices = {
        p["ticker"]: p
        for p in (client.table("market_prices").select("*").execute().data or [])
    }
    usdkrw_row = prices.get("USDKRW")
    usdkrw = float(usdkrw_row["price"]) if usdkrw_row else None
    amap = _account_map(client)

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
        acct_id = str(h.get("account_id") or "")
        inst = amap.get(acct_id, "계좌")
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
                "account_id": acct_id,
                "institution": inst,
                "label": f"{h['ticker']} · {inst}",
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


def _aggregate_ticker(rows: list[dict]) -> dict:
    """Sum quantities/values across accounts; quantity-weighted average cost."""
    if not rows:
        return {}
    qty = sum(float(r.get("qty") or 0) for r in rows)
    cost = sum(float(r.get("qty") or 0) * float(r.get("avg") or 0) for r in rows)
    value_rows = [r for r in rows if r.get("value") is not None]
    value = sum(float(r["value"]) for r in value_rows) if value_rows else None
    price = next((r.get("price") for r in rows if r.get("price") is not None), None)
    ccy = rows[0].get("ccy") or "USD"
    wavg = (cost / qty) if qty else None
    ret = ((float(price) - wavg) / wavg * 100) if price is not None and wavg else None
    return {
        "ticker": rows[0]["ticker"],
        "name": rows[0].get("name"),
        "qty": qty,
        "avg": wavg,
        "price": price,
        "value": value,
        "return_%": ret,
        "ccy": ccy,
        "accounts": len(rows),
    }


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
        # Aggregate same ticker across accounts for composition
        by_ticker: dict[str, float] = {}
        for r in live_rows:
            if r.get("value") is None:
                continue
            by_ticker[r["ticker"]] = by_ticker.get(r["ticker"], 0.0) + float(r["value"])
        if by_ticker:
            pdf = pd.DataFrame([{"ticker": k, "value": v} for k, v in by_ticker.items()])
            fig = px.pie(
                pdf,
                names="ticker",
                values="value",
                color_discrete_sequence=CHART_COLORS,
                hole=0.45,
            )
            fig.update_layout(**chart_layout(300, with_title=True), title="실시간 평가 (종목 합산)")
            show_plotly(fig)
        elif not hdf.empty:
            latest = hdf["snapshot_date"].max()
            day = (
                hdf[hdf["snapshot_date"] == latest]
                .dropna(subset=["market_value_krw"])
                .groupby("ticker", as_index=False)["market_value_krw"]
                .sum()
            )
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
        else:
            st.info("보유 종목이 없습니다.")

    # Compact return bars — blended per ticker across accounts
    if live_rows:
        st.markdown("##### 종목 수익률 (계좌 합산)")
        groups: dict[str, list] = {}
        for r in live_rows:
            groups.setdefault(r["ticker"], []).append(r)
        agg = [_aggregate_ticker(v) for v in groups.values()]
        rdf = pd.DataFrame(agg).dropna(subset=["return_%"])
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
    """All tickers or one ticker; always show per-account rows + cross-account totals."""
    hdf = _load_holding_snaps(client)
    amap = _account_map(client)
    if not hdf.empty and "account_id" in hdf.columns:
        hdf = hdf.copy()
        hdf["account_id"] = hdf["account_id"].astype(str)
        hdf["institution"] = hdf["account_id"].map(lambda i: amap.get(i, "계좌"))
        hdf["series"] = hdf.apply(
            lambda r: f"{r['ticker']} · {r['institution']}", axis=1
        )

    tickers = sorted({r["ticker"] for r in live_rows}) or (
        sorted(hdf["ticker"].unique().tolist()) if not hdf.empty else []
    )
    if not tickers and not live_rows:
        st.info("표시할 종목이 없습니다.")
        return

    pick = st.selectbox(
        "종목 보기",
        options=["(전체)"] + tickers,
        help="전체를 한눈에 보거나, 한 종목을 골라 계좌별·합계를 확인하세요.",
    )

    if pick == "(전체)":
        _view_all_tickers(live_rows, hdf)
    else:
        _view_one_ticker(pick, live_rows, hdf)


def _view_all_tickers(live_rows: list[dict], hdf: pd.DataFrame) -> None:
    st.caption("동일 종목이 여러 계좌에 있으면 계좌별로 나누고, 종목 합계도 함께 표시합니다.")

    groups: dict[str, list] = {}
    for r in live_rows:
        groups.setdefault(r["ticker"], []).append(r)

    # Summary metrics: ticker totals
    summary_rows = []
    for ticker, rows in sorted(groups.items()):
        tot = _aggregate_ticker(rows)
        summary_rows.append(
            {
                "티커": ticker,
                "종목명": tot.get("name"),
                "계좌수": tot.get("accounts"),
                "합산수량": tot.get("qty"),
                "가중평균단가": tot.get("avg"),
                "현재가": tot.get("price"),
                "합산평가액": tot.get("value"),
                "수익률(%)": tot.get("return_%"),
                "통화": tot.get("ccy"),
            }
        )
    if summary_rows:
        st.markdown("##### 종목 합계")
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    # Per-account detail table
    detail_rows = [
        {
            "티커": r["ticker"],
            "계좌": r.get("institution"),
            "수량": r.get("qty"),
            "평균단가": r.get("avg"),
            "현재가": r.get("price"),
            "평가액": r.get("value"),
            "수익률(%)": r.get("return_%"),
            "통화": r.get("ccy"),
            "시세": r.get("시세"),
        }
        for r in sorted(live_rows, key=lambda x: (x["ticker"], x.get("institution") or ""))
    ]
    if detail_rows:
        st.markdown("##### 계좌별 상세")
        st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)

    # Charts: per account-ticker series + ticker totals
    if not hdf.empty and "market_value_krw" in hdf.columns:
        plot_df = hdf.dropna(subset=["market_value_krw"]).copy()
        if not plot_df.empty:
            st.markdown("##### 계좌·종목별 평가액 추이")
            color_col = "series" if "series" in plot_df.columns else "ticker"
            fig = px.line(
                plot_df,
                x="snapshot_date",
                y="market_value_krw",
                color=color_col,
                markers=True,
                color_discrete_sequence=CHART_COLORS,
                labels={
                    "snapshot_date": "날짜",
                    "market_value_krw": "평가액(원)",
                    color_col: "종목·계좌",
                },
            )
            fig.update_layout(**chart_layout(320, with_title=True), title="계좌별 라인")
            show_plotly(fig)

            st.markdown("##### 종목 합산 추이")
            summed = (
                plot_df.groupby(["snapshot_date", "ticker"], as_index=False)["market_value_krw"]
                .sum()
            )
            fig2 = px.line(
                summed,
                x="snapshot_date",
                y="market_value_krw",
                color="ticker",
                markers=True,
                color_discrete_sequence=CHART_COLORS,
                labels={
                    "snapshot_date": "날짜",
                    "market_value_krw": "평가액(원)",
                    "ticker": "종목",
                },
            )
            fig2.update_layout(**chart_layout(300, with_title=True), title="종목 합계 (전 계좌)")
            show_plotly(fig2)


def _view_one_ticker(ticker: str, live_rows: list[dict], hdf: pd.DataFrame) -> None:
    rows = [r for r in live_rows if r["ticker"] == ticker]
    if not rows and not hdf.empty:
        # Fall back to snapshot-only tickers
        snap = hdf[hdf["ticker"] == ticker]
        if snap.empty:
            st.info("이 종목 데이터가 없습니다.")
            return

    tot = _aggregate_ticker(rows) if rows else {}
    st.markdown(f"##### {ticker} 합계 ({tot.get('accounts', 0)}개 계좌)")
    a, b, c, d = st.columns(4, gap="small")
    a.metric(
        "합산 수량",
        f"{float(tot['qty']):,.4f}".rstrip("0").rstrip(".") if tot.get("qty") is not None else "—",
    )
    b.metric("현재가", _fmt_money(tot.get("price"), tot.get("ccy") or "USD"))
    c.metric("합산 평가액", _fmt_money(tot.get("value"), tot.get("ccy") or "USD"))
    d.metric(
        "합산 수익률",
        f"{tot['return_%']:.2f}%" if tot.get("return_%") is not None else "—",
    )
    if tot.get("avg") is not None:
        st.caption(f"가중평균단가: {_fmt_money(tot['avg'], tot.get('ccy') or 'USD')}")

    st.markdown("##### 계좌별")
    for r in sorted(rows, key=lambda x: x.get("institution") or ""):
        with st.container():
            st.markdown(f"**{r.get('institution') or '계좌'}**")
            c1, c2, c3, c4 = st.columns(4, gap="small")
            c1.metric("수량", f"{float(r['qty']):,.4f}".rstrip("0").rstrip("."))
            c2.metric("평균단가", _fmt_money(r.get("avg"), r.get("ccy") or "USD"))
            c3.metric("평가액", _fmt_money(r.get("value"), r.get("ccy") or "USD"))
            c4.metric(
                "수익률",
                f"{r['return_%']:.2f}%" if r.get("return_%") is not None else "—",
            )

    if hdf.empty:
        st.info("이 종목의 일별 스냅샷이 아직 없습니다.")
        return

    one = hdf[hdf["ticker"] == ticker].sort_values("snapshot_date")
    if one.empty:
        st.info("이 종목의 일별 스냅샷이 아직 없습니다.")
        return

    # Per-account history
    if "institution" in one.columns and one["account_id"].nunique() > 1:
        st.markdown("##### 계좌별 평가액 추이")
        fig = px.line(
            one.dropna(subset=["market_value_krw"]),
            x="snapshot_date",
            y="market_value_krw",
            color="institution",
            markers=True,
            color_discrete_sequence=CHART_COLORS,
            labels={
                "snapshot_date": "날짜",
                "market_value_krw": "평가액(원)",
                "institution": "계좌",
            },
        )
        fig.update_layout(**chart_layout(300, with_title=True), title=f"{ticker} 계좌별")
        show_plotly(fig)

    # Combined total history
    st.markdown("##### 합산 평가액 · 가격")
    summed = (
        one.groupby("snapshot_date", as_index=False)
        .agg(
            market_value_krw=("market_value_krw", "sum"),
            price=("price", "mean"),
        )
        .sort_values("snapshot_date")
    )
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=summed["snapshot_date"],
            y=summed["market_value_krw"],
            name="합산 평가액(원)",
            mode="lines+markers",
            line=dict(color=PRIMARY, width=3),
            yaxis="y1",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=summed["snapshot_date"],
            y=summed["price"],
            name="가격",
            mode="lines+markers",
            line=dict(color="#00A3FF", width=2),
            yaxis="y2",
        )
    )
    fig.update_layout(
        **chart_layout(320, with_title=True),
        title=f"{ticker} 합산 일별 추이",
        yaxis=dict(title="평가액(원)"),
        yaxis2=dict(title="가격", overlaying="y", side="right"),
    )
    show_plotly(fig)


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
