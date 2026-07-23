"""Dashboard hub: overview / holdings / PnL / asset-flow charts (read-only)."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.asset_flows_ui import render_flow_charts  # noqa: E402
from lib.auth import ensure_profile, require_auth  # noqa: E402
from lib.chart_period import filter_by_period, period_radio  # noqa: E402
from lib.debt_ui import render_debt_dashboard  # noqa: E402
from lib.market_data import STALE_HOURS, is_stale  # noqa: E402
from lib.realized_pnl_ui import render_total_realized_pnl  # noqa: E402
from lib.tax_ui import render_tax_dashboard  # noqa: E402
from lib.theme import (  # noqa: E402
    PRIMARY,
    apply_theme,
    chart_layout,
    networth_banner,
    page_hero,
    render_subnav,
    show_plotly,
)

apply_theme(max_width=1280)

VIEWS = ["홈", "보유", "손익", "거래", "부채", "세금"]


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


def _status_bar(*, any_stale: bool) -> None:
    """Read-only status — price/snapshot jobs live under 자산 챗."""
    stale = " · 시세 지연" if any_stale else ""
    st.caption(
        f"조회 전용{stale} · 시세/스냅샷·브리핑은 「자산 챗」에서 "
        f"({STALE_HOURS:.0f}시간 초과 시 지연 표시)"
    )


def _html_escape(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _fmt_qty(q) -> str:
    if q is None:
        return "—"
    try:
        n = float(q)
    except (TypeError, ValueError):
        return "—"
    return f"{n:,.4f}".rstrip("0").rstrip(".")


def _holding_rows_html(items: list[dict]) -> str:
    """Toss-style holding list (not a raw DB table)."""
    parts = ['<div class="np-hold-list">']
    for it in items:
        ticker = _html_escape(it.get("ticker") or "")
        name = _html_escape(it.get("name") or it.get("ticker") or "")
        meta = _html_escape(it.get("meta") or "")
        value = _html_escape(it.get("value_label") or "—")
        ret = it.get("return_%")
        if ret is None:
            ret_cls, ret_txt = "flat", "—"
        elif ret > 0.05:
            ret_cls, ret_txt = "up", f"+{ret:.2f}%"
        elif ret < -0.05:
            ret_cls, ret_txt = "down", f"{ret:.2f}%"
        else:
            ret_cls, ret_txt = "flat", f"{ret:.2f}%"
        meta_bit = f" · {meta}" if meta else ""
        parts.append(
            '<div class="np-hold-row">'
            '<div class="np-hold-left">'
            f'<div class="np-hold-ticker">{ticker}</div>'
            f'<div class="np-hold-meta">{name}{meta_bit}</div>'
            "</div>"
            '<div class="np-hold-right">'
            f'<div class="np-hold-value">{value}</div>'
            f'<div class="np-hold-ret {ret_cls}">{ret_txt}</div>'
            "</div>"
            "</div>"
        )
    parts.append("</div>")
    return "\n".join(parts)


def view_home(client, live_rows, total_usd, total_krw, total_debt, any_stale) -> None:
    """홈: 순자산 + 추이 1개 + 상위 보유 리스트."""
    net_krw = (total_krw - total_debt) if total_krw else None
    networth_banner(
        "추정 순자산",
        _fmt_money(net_krw, "KRW") if net_krw is not None else "—",
        sub=f"투자 {_fmt_money(total_krw, 'KRW') if total_krw else '—'} · 부채 {_fmt_money(total_debt, 'KRW')}",
    )
    m1, m2, m3 = st.columns(3, gap="small")
    m1.metric("투자자산 (달러)", _fmt_money(total_usd, "USD") if total_usd else "—")
    m2.metric("투자자산 (원)", _fmt_money(total_krw, "KRW") if total_krw else "—")
    m3.metric("부채", _fmt_money(total_debt, "KRW"))
    if any_stale:
        st.caption("일부 시세가 지연되었습니다. 상단에서 시세를 새로고침하세요.")

    months = period_radio(key="dash_period_home", default="1년")
    tdf = filter_by_period(_load_daily_totals(client), months, date_col="snapshot_date")
    if not tdf.empty:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=tdf["snapshot_date"],
                y=tdf["net_assets"],
                name="순자산",
                mode="lines",
                line=dict(color=PRIMARY, width=2.5),
                fill="tozeroy",
                fillcolor="rgba(3,199,90,0.10)",
            )
        )
        fig.update_layout(**chart_layout(220, with_title=True), title="순자산 추이", yaxis_title="원")
        show_plotly(fig)
    else:
        st.info("스냅샷이 없습니다. 「오늘 스냅샷」을 눌러 시작하세요.")

    groups: dict[str, list] = {}
    for r in live_rows:
        groups.setdefault(r["ticker"], []).append(r)
    preview = []
    for ticker, rows in groups.items():
        tot = _aggregate_ticker(rows)
        preview.append(
            {
                "ticker": ticker,
                "name": tot.get("name") or ticker,
                "meta": f"{tot.get('accounts', 1)}개 계좌",
                "value_label": _fmt_money(tot.get("value"), tot.get("ccy") or "USD"),
                "return_%": tot.get("return_%"),
                "sort": float(tot.get("value") or 0),
            }
        )
    preview.sort(key=lambda x: x["sort"], reverse=True)
    st.caption("보유 상위")
    if preview:
        st.markdown(_holding_rows_html(preview[:8]), unsafe_allow_html=True)
    else:
        st.info("보유 종목이 없습니다.")


def view_holdings(client, live_rows) -> None:
    """보유: 토스식 조회 리스트 (DB 테이블 직접 노출 없음)."""
    if not live_rows:
        st.info("표시할 보유가 없습니다.")
        return

    institutions = sorted({r.get("institution") or "계좌" for r in live_rows})
    c1, c2, c3 = st.columns([1.4, 1, 1], gap="small")
    with c1:
        q = st.text_input("검색", placeholder="티커 또는 종목명", label_visibility="collapsed")
    with c2:
        acct = st.selectbox("계좌", ["전체"] + institutions, label_visibility="collapsed")
    with c3:
        sort_by = st.selectbox("정렬", ["평가액", "수익률", "가나다"], label_visibility="collapsed")

    rows = live_rows
    if acct != "전체":
        rows = [r for r in rows if (r.get("institution") or "계좌") == acct]
    if q:
        qq = q.strip().lower()
        rows = [
            r
            for r in rows
            if qq in str(r.get("ticker") or "").lower()
            or qq in str(r.get("name") or "").lower()
        ]

    groups: dict[str, list] = {}
    for r in rows:
        groups.setdefault(r["ticker"], []).append(r)

    items = []
    for ticker, gro in groups.items():
        tot = _aggregate_ticker(gro)
        items.append(
            {
                "ticker": ticker,
                "name": tot.get("name") or ticker,
                "meta": f"{_fmt_qty(tot.get('qty'))}주 · {tot.get('accounts', 1)}계좌",
                "value_label": _fmt_money(tot.get("value"), tot.get("ccy") or "USD"),
                "return_%": tot.get("return_%"),
                "value": float(tot.get("value") or 0),
                "ret": float(tot.get("return_%") if tot.get("return_%") is not None else -9999),
                "accounts": gro,
                "tot": tot,
            }
        )

    if sort_by == "평가액":
        items.sort(key=lambda x: x["value"], reverse=True)
    elif sort_by == "수익률":
        items.sort(key=lambda x: x["ret"], reverse=True)
    else:
        items.sort(key=lambda x: x["ticker"])

    st.caption(f"{len(items)}종목")
    st.markdown(_holding_rows_html(items), unsafe_allow_html=True)

    tickers = [i["ticker"] for i in items]
    if not tickers:
        st.info("검색 결과가 없습니다.")
        return

    pick = st.selectbox("상세 보기", tickers, key="hold_detail_ticker")
    chosen = next(i for i in items if i["ticker"] == pick)
    tot = chosen["tot"]
    a, b, c, d = st.columns(4, gap="small")
    a.metric("수량", _fmt_qty(tot.get("qty")))
    b.metric("평균단가", _fmt_money(tot.get("avg"), tot.get("ccy") or "USD"))
    c.metric("현재가", _fmt_money(tot.get("price"), tot.get("ccy") or "USD"))
    d.metric("수익률", f"{tot['return_%']:.2f}%" if tot.get("return_%") is not None else "—")

    acc_items = []
    for r in sorted(chosen["accounts"], key=lambda x: x.get("institution") or ""):
        acc_items.append(
            {
                "ticker": r.get("institution") or "계좌",
                "name": pick,
                "meta": f"{_fmt_qty(r.get('qty'))}주 · 평단 {_fmt_money(r.get('avg'), r.get('ccy') or 'USD')}",
                "value_label": _fmt_money(r.get("value"), r.get("ccy") or "USD"),
                "return_%": r.get("return_%"),
            }
        )
    st.caption("계좌별")
    st.markdown(_holding_rows_html(acc_items), unsafe_allow_html=True)

    months = period_radio(key="dash_period_holdings", default="1년")
    hdf = filter_by_period(_load_holding_snaps(client), months, date_col="snapshot_date")
    if hdf.empty or "market_value_krw" not in hdf.columns:
        st.caption("선택한 기간에 평가액 추이가 없습니다.")
        return
    one = hdf[hdf["ticker"] == pick].sort_values("snapshot_date")
    if one.empty:
        st.caption("이 종목의 추이 데이터가 없습니다.")
        return
    summed = one.groupby("snapshot_date", as_index=False)["market_value_krw"].sum()
    fig = go.Figure(
        go.Scatter(
            x=summed["snapshot_date"],
            y=summed["market_value_krw"],
            mode="lines",
            line=dict(color=PRIMARY, width=2.5),
            fill="tozeroy",
            fillcolor="rgba(3,199,90,0.10)",
            name="평가액(원)",
        )
    )
    fig.update_layout(**chart_layout(220, with_title=True), title=f"{pick} 평가액", yaxis_title="원")
    show_plotly(fig)


def main() -> None:
    page_hero(
        "대시보드",
        "순자산·보유·손익·거래·부채·세금을 조회합니다. 입력은 「기록하기」에서만 합니다.",
        compact=True,
    )
    view = render_subnav(VIEWS, state_key="dash_view", default="홈")

    user, client = require_auth()
    ensure_profile(user, client)

    holdings = client.table("holdings").select("*").execute().data or []
    live_rows, total_usd, total_krw, total_debt, any_stale = _live_holdings(client, holdings)

    if view in ("홈", "보유"):
        _status_bar(any_stale=any_stale)

    if view == "홈":
        view_home(client, live_rows, total_usd, total_krw, total_debt, any_stale)
    elif view == "보유":
        view_holdings(client, live_rows)
    elif view == "손익":
        render_total_realized_pnl(client, compact=False)
    elif view == "거래":
        render_flow_charts(client)
    elif view == "부채":
        render_debt_dashboard(client)
    else:
        render_tax_dashboard(client)


main()
