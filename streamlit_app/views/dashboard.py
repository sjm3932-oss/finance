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


def _account_options(client, live_rows: list[dict]) -> list[str]:
    """전체 + institutions from accounts table (fallback: live holdings)."""
    amap = _account_map(client)
    names = sorted({n for n in amap.values() if n})
    if not names:
        names = sorted({r.get("institution") or "계좌" for r in live_rows})
    return ["전체"] + names


def _filter_by_account(live_rows: list[dict], account_label: str) -> list[dict]:
    if not account_label or account_label == "전체":
        return list(live_rows)
    return [r for r in live_rows if (r.get("institution") or "계좌") == account_label]


def _to_krw(amount: float | None, ccy: str, usdkrw: float | None) -> float | None:
    if amount is None:
        return None
    if (ccy or "KRW") == "USD":
        return float(amount) * usdkrw if usdkrw else None
    return float(amount)


def _portfolio_stats(
    live_rows: list[dict], usdkrw: float | None
) -> dict[str, float | None]:
    """Aggregate evaluation, cost basis, and total return % in KRW."""
    value_krw = 0.0
    cost_krw = 0.0
    has_value = False
    has_cost = False
    for r in live_rows:
        ccy = r.get("ccy") or "USD"
        qty = float(r.get("qty") or 0)
        avg = float(r.get("avg") or 0)
        mv = r.get("value")
        v = _to_krw(float(mv) if mv is not None else None, ccy, usdkrw)
        c = _to_krw(qty * avg if qty and avg else None, ccy, usdkrw)
        if v is not None:
            value_krw += v
            has_value = True
        if c is not None:
            cost_krw += c
            has_cost = True
    ret = None
    if has_cost and cost_krw > 0 and has_value:
        ret = (value_krw - cost_krw) / cost_krw * 100.0
    return {
        "value_krw": value_krw if has_value else None,
        "cost_krw": cost_krw if has_cost else None,
        "return_%": ret,
        "pnl_krw": (value_krw - cost_krw) if (has_value and has_cost) else None,
    }


def _render_account_selector(client, live_rows: list[dict]) -> str:
    options = _account_options(client, live_rows)
    current = st.session_state.get("dash_account_filter")
    if current not in options:
        st.session_state.dash_account_filter = "전체"
    return st.selectbox(
        "계좌",
        options,
        key="dash_account_filter",
        help="선택한 증권사 계좌의 보유만 표시합니다.",
    )


def _render_return_header(account_label: str, stats: dict[str, float | None]) -> None:
    ret = stats.get("return_%")
    if ret is None:
        ret_txt = "—"
    else:
        sign = "+" if ret > 0.005 else ""
        ret_txt = f"{sign}{ret:.2f}%"
    title = (
        f"{account_label} · 총 투자수익률"
        if account_label and account_label != "전체"
        else "총 투자수익률"
    )
    sub_parts = []
    if stats.get("value_krw") is not None:
        sub_parts.append(f"평가 {_fmt_money(stats['value_krw'], 'KRW')}")
    if stats.get("cost_krw") is not None:
        sub_parts.append(f"원금 {_fmt_money(stats['cost_krw'], 'KRW')}")
    if stats.get("pnl_krw") is not None:
        pnl = stats["pnl_krw"]
        sign = "+" if pnl > 0 else ""
        sub_parts.append(f"손익 {sign}{_fmt_money(pnl, 'KRW')}")
    networth_banner(title, ret_txt, sub=" · ".join(sub_parts))
    st.caption("평가액 ÷ 매입원금 기준 미실현 수익률입니다.")


def _live_holdings(client, holdings: list[dict]) -> tuple[list[dict], float, float, float, bool, float | None]:
    from lib.symbol_resolve import enrich_holdings_names

    holdings = enrich_holdings_names(client, holdings, persist=True)

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
                "cost": qty * avg if qty and avg else None,
                "ccy": cur,
                "시세": "지연" if stale else ("없음" if price is None else "정상"),
            }
        )

    debts = client.table("debts").select("principal").execute().data or []
    total_debt = sum(float(d.get("principal") or 0) for d in debts)
    return live_rows, total_usd, total_krw, total_debt, any_stale, usdkrw


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
        "name": next(
            (
                r.get("name")
                for r in rows
                if r.get("name")
                and str(r.get("name")).strip().upper() != str(r.get("ticker") or "").strip().upper()
            ),
            rows[0].get("name"),
        ),
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
    """Toss-style holding list (not a raw DB table). Name on top, ticker in meta."""
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
        # Subline: ticker first so KR stocks stay identifiable under the name
        sub = ticker
        if meta:
            sub = f"{ticker} · {meta}" if ticker else meta
        parts.append(
            '<div class="np-hold-row">'
            '<div class="np-hold-left">'
            f'<div class="np-hold-ticker">{name}</div>'
            f'<div class="np-hold-meta">{sub}</div>'
            "</div>"
            '<div class="np-hold-right">'
            f'<div class="np-hold-value">{value}</div>'
            f'<div class="np-hold-ret {ret_cls}">{ret_txt}</div>'
            "</div>"
            "</div>"
        )
    parts.append("</div>")
    return "\n".join(parts)


def view_home(
    client,
    live_rows,
    total_debt,
    any_stale,
    *,
    account_label: str,
    stats: dict,
) -> None:
    """홈: 계좌별 총 수익률 + 추이 + 보유 리스트."""
    _render_return_header(account_label, stats)

    m1, m2, m3 = st.columns(3, gap="small")
    m1.metric("평가액", _fmt_money(stats.get("value_krw"), "KRW") if stats.get("value_krw") is not None else "—")
    m2.metric("매입원금", _fmt_money(stats.get("cost_krw"), "KRW") if stats.get("cost_krw") is not None else "—")
    if account_label == "전체":
        m3.metric("부채", _fmt_money(total_debt, "KRW"))
    else:
        pnl = stats.get("pnl_krw")
        m3.metric(
            "평가손익",
            (f"+{_fmt_money(pnl, 'KRW')}" if pnl is not None and pnl >= 0 else _fmt_money(pnl, "KRW"))
            if pnl is not None
            else "—",
        )
    if any_stale:
        st.caption("일부 시세가 지연되었습니다. 「자산 챗」에서 시세를 새로고침하세요.")

    months = period_radio(key="dash_period_home", default="1년")
    account_ids = {
        r.get("account_id") for r in live_rows if r.get("account_id")
    }

    # Account-scoped chart from holding snapshots; whole-portfolio uses daily_snapshots
    if account_label != "전체" and account_ids:
        hdf = filter_by_period(_load_holding_snaps(client, days=400), months, date_col="snapshot_date")
        if not hdf.empty and "account_id" in hdf.columns:
            hdf = hdf[hdf["account_id"].astype(str).isin(account_ids)]
        if not hdf.empty and "market_value_krw" in hdf.columns:
            summed = (
                hdf.groupby("snapshot_date", as_index=False)["market_value_krw"]
                .sum()
                .sort_values("snapshot_date")
            )
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=summed["snapshot_date"],
                    y=summed["market_value_krw"],
                    name="평가액",
                    mode="lines",
                    line=dict(color=PRIMARY, width=2.5),
                    fill="tozeroy",
                    fillcolor="rgba(3,199,90,0.10)",
                )
            )
            fig.update_layout(
                **chart_layout(220, with_title=True),
                title=f"{account_label} 평가액 추이",
                yaxis_title="원",
            )
            show_plotly(fig)
        else:
            st.info("이 계좌의 스냅샷이 없습니다. 「자산 챗」에서 오늘 스냅샷을 만들어 보세요.")
    else:
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
            st.info("스냅샷이 없습니다. 「자산 챗」에서 오늘 스냅샷을 만들어 보세요.")

    groups: dict[str, list] = {}
    for r in live_rows:
        groups.setdefault(r["ticker"], []).append(r)
    preview = []
    for ticker, rows in groups.items():
        tot = _aggregate_ticker(rows)
        meta = f"{_fmt_qty(tot.get('qty'))}주"
        if account_label == "전체" and tot.get("accounts", 1) > 1:
            meta = f"{meta} · {tot.get('accounts')}개 계좌"
        preview.append(
            {
                "ticker": ticker,
                "name": tot.get("name") or ticker,
                "meta": meta,
                "value_label": _fmt_money(tot.get("value"), tot.get("ccy") or "USD"),
                "return_%": tot.get("return_%"),
                "sort": float(tot.get("value") or 0),
            }
        )
    preview.sort(key=lambda x: x["sort"], reverse=True)
    st.caption(f"보유 {len(preview)}종목" + (f" · {account_label}" if account_label != "전체" else ""))
    if preview:
        st.markdown(_holding_rows_html(preview[:12]), unsafe_allow_html=True)
    else:
        st.info("이 계좌에 표시할 보유 종목이 없습니다.")


def view_holdings(
    client,
    live_rows,
    *,
    account_label: str,
    stats: dict,
) -> None:
    """보유: 선택한 계좌의 종목 리스트 + 총 수익률."""
    _render_return_header(account_label, stats)

    if not live_rows:
        st.info("이 계좌에 표시할 보유가 없습니다.")
        return

    c1, c2 = st.columns([1.6, 1], gap="small")
    with c1:
        q = st.text_input("검색", placeholder="티커 또는 종목명", label_visibility="collapsed")
    with c2:
        sort_by = st.selectbox("정렬", ["평가액", "수익률", "가나다"], label_visibility="collapsed")

    rows = live_rows
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
        meta = f"{_fmt_qty(tot.get('qty'))}주"
        if account_label == "전체" and tot.get("accounts", 1) > 1:
            meta = f"{meta} · {tot.get('accounts')}계좌"
        elif account_label != "전체":
            meta = f"{meta} · {account_label}"
        items.append(
            {
                "ticker": ticker,
                "name": tot.get("name") or ticker,
                "meta": meta,
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
        items.sort(key=lambda x: (x.get("name") or x["ticker"]))

    st.caption(f"{len(items)}종목")
    st.markdown(_holding_rows_html(items), unsafe_allow_html=True)

    tickers = [i["ticker"] for i in items]
    if not tickers:
        st.info("검색 결과가 없습니다.")
        return

    labels = {
        i["ticker"]: (
            f"{i['name']} ({i['ticker']})"
            if i.get("name") and i["name"] != i["ticker"]
            else i["ticker"]
        )
        for i in items
    }
    pick = st.selectbox(
        "상세 보기",
        tickers,
        format_func=lambda t: labels.get(t, t),
        key="hold_detail_ticker",
    )
    chosen = next(i for i in items if i["ticker"] == pick)
    tot = chosen["tot"]
    a, b, c, d = st.columns(4, gap="small")
    a.metric("수량", _fmt_qty(tot.get("qty")))
    b.metric("평균단가", _fmt_money(tot.get("avg"), tot.get("ccy") or "USD"))
    c.metric("현재가", _fmt_money(tot.get("price"), tot.get("ccy") or "USD"))
    d.metric("수익률", f"{tot['return_%']:.2f}%" if tot.get("return_%") is not None else "—")

    if account_label == "전체":
        acc_items = []
        for r in sorted(chosen["accounts"], key=lambda x: x.get("institution") or ""):
            acc_items.append(
                {
                    "ticker": "",
                    "name": r.get("institution") or "계좌",
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
    one = hdf[hdf["ticker"] == pick]
    if account_label != "전체":
        ids = {r.get("account_id") for r in chosen["accounts"] if r.get("account_id")}
        if ids and "account_id" in one.columns:
            one = one[one["account_id"].astype(str).isin(ids)]
    one = one.sort_values("snapshot_date")
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
    title_name = chosen.get("name") or pick
    fig.update_layout(
        **chart_layout(220, with_title=True),
        title=f"{title_name} 평가액",
        yaxis_title="원",
    )
    show_plotly(fig)


def main() -> None:
    page_hero(
        "내 자산",
        "계좌를 고르면 그 증권사 보유만 보고, 상단에 총 투자수익률이 표시됩니다.",
        compact=True,
    )
    view = render_subnav(VIEWS, state_key="dash_view", default="홈")

    user, client = require_auth()
    ensure_profile(user, client)

    holdings = client.table("holdings").select("*").execute().data or []
    live_rows, _total_usd, _total_krw, total_debt, any_stale, usdkrw = _live_holdings(
        client, holdings
    )

    if view in ("홈", "보유"):
        _status_bar(any_stale=any_stale)
        account_label = _render_account_selector(client, live_rows)
        filtered = _filter_by_account(live_rows, account_label)
        stats = _portfolio_stats(filtered, usdkrw)
        if view == "홈":
            view_home(
                client,
                filtered,
                total_debt,
                any_stale,
                account_label=account_label,
                stats=stats,
            )
        else:
            view_holdings(
                client,
                filtered,
                account_label=account_label,
                stats=stats,
            )
    elif view == "손익":
        render_total_realized_pnl(client, compact=False)
    elif view == "거래":
        render_flow_charts(client)
    elif view == "부채":
        render_debt_dashboard(client)
    else:
        render_tax_dashboard(client)


main()
