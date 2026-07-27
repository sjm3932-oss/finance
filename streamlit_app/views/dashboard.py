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

from lib.account_filter import (  # noqa: E402
    account_ids_for_label,
    render_account_selector,
)
from lib.asset_flows_ui import render_flow_charts  # noqa: E402
from lib.auth import ensure_profile, require_auth  # noqa: E402
from lib.chart_period import filter_by_period, period_radio  # noqa: E402
from lib.debt_ui import render_debt_dashboard  # noqa: E402
from lib.export_csv import download_csv_button  # noqa: E402
from lib.market_data import is_stale  # noqa: E402
from lib.net_worth import (  # noqa: E402
    OWNERSHIP_KO,
    compute_net_worth,
    load_accounts_enriched,
    load_other_assets,
    monthly_summary_stats,
)
from lib.other_assets_ui import (  # noqa: E402
    render_allocation_drift,
    render_cash_accounts_panel,
    render_other_assets_dashboard,
)
from lib.portfolio_insights import (  # noqa: E402
    period_change_stats,
    realized_pnl_ytd_krw,
    render_allocation,
    render_benchmark_chart,
    render_dividend_calendar,
    render_period_change_row,
    render_pnl_split,
)
from lib.realized_pnl_ui import render_total_realized_pnl  # noqa: E402
from lib.tax_ui import render_tax_dashboard  # noqa: E402
from lib.theme import (  # noqa: E402
    PRIMARY,
    apply_theme,
    chart_layout,
    networth_banner,
    page_hero,
    render_grouped_asset_nav,
    show_plotly,
)
from lib.ticker_history import render_ticker_history  # noqa: E402
from lib.ux import (  # noqa: E402
    empty_cta,
    fmt_krw,
    render_abbrev_toggle,
    render_price_status_bar,
    ret_class,
    section_header,
)
from lib.watchlist_ui import evaluate_alerts, render_alert_banners, render_watchlist_panel  # noqa: E402
from lib.wealth_alerts import (  # noqa: E402
    evaluate_wealth_alerts,
    render_monthly_summary,
    render_wealth_alert_banners,
)

apply_theme(max_width=1280)

# Resolved views from grouped nav: 홈/보유/손익/배당/거래/관심/부채/세금


def _fmt_money(v, currency="KRW", *, signed: bool = False) -> str:
    from lib.ux import fmt_money

    return fmt_money(v, currency or "KRW", signed=signed)


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


def _filter_live_by_account_ids(
    live_rows: list[dict], account_ids: list[str] | None
) -> list[dict]:
    if account_ids is None:
        return list(live_rows)
    allow = {str(a) for a in account_ids}
    return [r for r in live_rows if str(r.get("account_id") or "") in allow]


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
        sub_parts.append(f"미실현 {_fmt_money(pnl, 'KRW', signed=True)}")
    tone = ret_class(stats.get("return_%"))
    networth_banner(title, ret_txt, sub=" · ".join(sub_parts), tone=tone)
    st.caption("평가액 ÷ 매입원금 기준 미실현 수익률입니다.")


def _summary_hero_html(
    account_label: str,
    stats: dict,
    change: dict,
    *,
    total_debt: float | None = None,
) -> str:
    """Legacy invest-return hero (보유 탭 등)."""
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
    tone = ret_class(ret)

    cells: list[tuple[str, str, str, str]] = []
    today_pnl = change.get("today_pnl")
    today_pct = change.get("today_pct")
    cells.append(
        (
            "오늘 손익",
            fmt_krw(today_pnl, signed=True) if today_pnl is not None else "—",
            ret_class(today_pct if today_pct is not None else today_pnl),
            f"{today_pct:+.2f}%" if today_pct is not None else "",
        )
    )
    cells.append(
        (
            "평가액",
            fmt_krw(stats.get("value_krw")) if stats.get("value_krw") is not None else "—",
            "flat",
            "",
        )
    )
    cells.append(
        (
            "매입원금",
            fmt_krw(stats.get("cost_krw")) if stats.get("cost_krw") is not None else "—",
            "flat",
            "",
        )
    )
    pnl = stats.get("pnl_krw")
    cells.append(
        (
            "미실현",
            fmt_krw(pnl, signed=True) if pnl is not None else "—",
            ret_class(pnl),
            "",
        )
    )
    if account_label == "전체":
        cells.append(
            (
                "부채",
                fmt_krw(total_debt) if total_debt is not None else "—",
                "flat",
                "",
            )
        )
    else:
        week_pnl = change.get("week_pnl")
        week_pct = change.get("week_pct")
        cells.append(
            (
                "이번 주",
                fmt_krw(week_pnl, signed=True) if week_pnl is not None else "—",
                ret_class(week_pct if week_pct is not None else week_pnl),
                f"{week_pct:+.2f}%" if week_pct is not None else "",
            )
        )

    cell_html = []
    for label, value, cell_tone, delta in cells:
        delta_html = (
            f'<div class="np-summary-hero-cell-delta">{_html_escape(delta)}</div>'
            if delta
            else ""
        )
        cell_html.append(
            "<div class='np-summary-hero-cell'>"
            f"<div class='np-summary-hero-cell-label'>{_html_escape(label)}</div>"
            f"<div class='np-summary-hero-cell-value {cell_tone}'>{_html_escape(value)}</div>"
            f"{delta_html}"
            "</div>"
        )

    return (
        '<div class="np-summary-hero">'
        f'<div class="np-summary-hero-label">{_html_escape(title)}</div>'
        f'<div class="np-summary-hero-ret {tone}">{_html_escape(ret_txt)}</div>'
        '<div class="np-summary-hero-sub">평가액 ÷ 매입원금 기준 미실현 수익률</div>'
        f'<div class="np-summary-hero-grid">{"".join(cell_html)}</div>'
        "</div>"
    )


def _networth_hero_html(
    account_label: str,
    nw: dict,
    change: dict,
    *,
    invest_ret: float | None,
) -> str:
    """Home hero centered on net worth composition."""
    title = (
        f"{account_label} · 순자산"
        if account_label and account_label != "전체"
        else "순자산"
    )
    net = nw.get("net")
    net_txt = fmt_krw(net) if net is not None else "—"
    today_pnl = change.get("today_pnl")
    today_pct = change.get("today_pct")
    tone = ret_class(today_pct if today_pct is not None else today_pnl)

    cells = [
        (
            "투자자산",
            fmt_krw(nw.get("invest")),
            "flat",
            "",
        ),
        (
            "현금",
            fmt_krw(nw.get("cash")),
            "flat",
            "",
        ),
        (
            "기타자산",
            fmt_krw(nw.get("other")),
            "flat",
            "",
        ),
        (
            "부채",
            fmt_krw(nw.get("debt")),
            "flat",
            "",
        ),
        (
            "오늘 손익",
            fmt_krw(today_pnl, signed=True) if today_pnl is not None else "—",
            ret_class(today_pct if today_pct is not None else today_pnl),
            f"{today_pct:+.2f}%" if today_pct is not None else "",
        ),
        (
            "투자수익률",
            (
                f"{'+' if (invest_ret or 0) > 0.005 else ''}{invest_ret:.2f}%"
                if invest_ret is not None
                else "—"
            ),
            ret_class(invest_ret),
            "",
        ),
    ]
    cell_html = []
    for label, value, cell_tone, delta in cells:
        delta_html = (
            f'<div class="np-summary-hero-cell-delta">{_html_escape(delta)}</div>'
            if delta
            else ""
        )
        cell_html.append(
            "<div class='np-summary-hero-cell'>"
            f"<div class='np-summary-hero-cell-label'>{_html_escape(label)}</div>"
            f"<div class='np-summary-hero-cell-value {cell_tone}'>{_html_escape(value)}</div>"
            f"{delta_html}"
            "</div>"
        )
    return (
        '<div class="np-summary-hero">'
        f'<div class="np-summary-hero-label">{_html_escape(title)}</div>'
        f'<div class="np-summary-hero-ret {tone}">{_html_escape(net_txt)}</div>'
        '<div class="np-summary-hero-sub">투자 + 현금 + 기타 − 부채</div>'
        f'<div class="np-summary-hero-grid">{"".join(cell_html)}</div>'
        "</div>"
    )


def _holding_initials(name: str | None, ticker: str | None) -> str:
    """1–2 char circle label from name or ticker."""
    src = (name or ticker or "?").strip()
    if not src:
        return "?"
    # Latin tickers (AAPL) → 2 letters; numeric KR tickers → last 2 digits
    compact = src.replace(".", "")
    if compact.isascii() and compact.isalpha() and len(compact) <= 6:
        return compact[:2].upper()
    if compact.isdigit() and len(compact) >= 2:
        return compact[-2:]
    letters = [c for c in src if c.isalnum()]
    if not letters:
        return src[:1]
    return letters[0].upper()


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


def _status_bar(client, *, any_stale: bool) -> None:
    """Price age chip + abbreviate toggle."""
    render_price_status_bar(client, any_stale=any_stale)
    render_abbrev_toggle()


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
        raw_ticker = it.get("ticker") or ""
        raw_name = it.get("name") or it.get("ticker") or ""
        ticker = _html_escape(raw_ticker)
        name = _html_escape(raw_name)
        meta = _html_escape(it.get("meta") or "")
        value = _html_escape(it.get("value_label") or "—")
        initials = _html_escape(_holding_initials(str(raw_name), str(raw_ticker)))
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
            f'<div class="np-hold-avatar" aria-hidden="true">{initials}</div>'
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
    account_ids: list[str] | None,
    stats: dict,
    usdkrw: float | None,
    ownership_filter: str | None = None,
) -> dict:
    """홈(요약): 순자산 중심 + 배분 드리프트 + 월간 요약."""
    accounts = load_accounts_enriched(client)
    other_assets = load_other_assets(client)
    debt_for_nw = float(total_debt or 0) if account_ids is None else 0.0
    nw = compute_net_worth(
        live_rows,
        accounts=accounts,
        other_assets=other_assets,
        total_debt=debt_for_nw,
        usdkrw=usdkrw,
        account_ids=account_ids,
        ownership=ownership_filter,
    )
    change = period_change_stats(client, stats.get("value_krw"), account_ids)
    st.markdown(
        _networth_hero_html(
            account_label,
            nw,
            change,
            invest_ret=stats.get("return_%"),
        ),
        unsafe_allow_html=True,
    )

    if change.get("today_pnl") is None:
        empty_cta(
            "오늘 손익을 보려면 일별 스냅샷이 필요합니다. 자동(자정)이거나 「자산 챗」에서 만들 수 있어요.",
            button_label="자산 챗에서 스냅샷 만들기",
            page_title="자산 챗",
            key="cta_snap_home",
        )

    month_stats = monthly_summary_stats(
        client, live_net=nw.get("net"), account_ids=account_ids
    )
    with st.expander("이번 달 요약", expanded=True):
        render_monthly_summary(client, nw, month_stats)

    realized = realized_pnl_ytd_krw(client, account_ids)
    with st.expander("미실현 · 실현 손익 자세히", expanded=False):
        render_pnl_split(unrealized=stats.get("pnl_krw"), realized_ytd=realized)

    with st.expander("자산 배분 · 목표 괴리", expanded=True):
        render_allocation_drift(client, nw)
        st.markdown("##### 종목 트리맵")
        render_allocation(live_rows, usdkrw)

    with st.expander("추이 · 벤치마크", expanded=False):
        months = period_radio(key="dash_period_home", default="1년")
        account_id_set = {
            r.get("account_id") for r in live_rows if r.get("account_id")
        }
        if account_label != "전체" and account_id_set:
            hdf = filter_by_period(
                _load_holding_snaps(client, days=400), months, date_col="snapshot_date"
            )
            if not hdf.empty and "account_id" in hdf.columns:
                hdf = hdf[hdf["account_id"].astype(str).isin(account_id_set)]
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
                    chart_layout(
                        220,
                        title=f"{account_label} 평가액 추이",
                        yaxis_title="원",
                    )
                )
                show_plotly(fig)
            else:
                empty_cta(
                    "이 계좌의 스냅샷이 없습니다.",
                    button_label="자산 챗으로 이동",
                    page_title="자산 챗",
                    key="cta_snap_acct",
                )
        else:
            tdf = filter_by_period(
                _load_daily_totals(client), months, date_col="snapshot_date"
            )
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
                fig.update_layout(
                    chart_layout(
                        220,
                        title="순자산 추이",
                        yaxis_title="원",
                    )
                )
                show_plotly(fig)
            else:
                empty_cta(
                    "스냅샷이 없습니다. 매일 자동으로 쌓이거나 지금 만들 수 있어요.",
                    button_label="자산 챗으로 이동",
                    page_title="자산 챗",
                    key="cta_snap_all",
                )
        section_header("벤치마크 비교")
        render_benchmark_chart(client, account_ids, months=months)

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
    section_header(
        "보유 미리보기",
        f"{len(preview)}종목"
        + (f" · {account_label}" if account_label != "전체" else ""),
    )
    if preview:
        st.markdown(_holding_rows_html(preview[:8]), unsafe_allow_html=True)
    else:
        empty_cta(
            "표시할 보유 종목이 없습니다. OCR·수기로 잔고를 등록하세요.",
            button_label="기록하기로 이동",
            page_title="기록하기",
            key="cta_record_home",
        )
    return nw


def view_networth_detail(client, live_rows, total_debt, *, usdkrw, account_ids, account_label) -> None:
    """더보기 → 순자산: 기타자산·현금·소유 구성."""
    accounts = load_accounts_enriched(client)
    other_assets = load_other_assets(client)
    nw = compute_net_worth(
        live_rows,
        accounts=accounts,
        other_assets=other_assets,
        total_debt=float(total_debt or 0) if account_ids is None else 0.0,
        usdkrw=usdkrw,
        account_ids=account_ids,
    )
    st.markdown(
        _networth_hero_html(account_label, nw, {}, invest_ret=None),
        unsafe_allow_html=True,
    )
    render_allocation_drift(client, nw)
    render_cash_accounts_panel(client)
    render_other_assets_dashboard(client, nw)


def view_other_assets(client, *, ownership_filter: str | None = None) -> None:
    """더보기 → 기타자산: 기타 자산만 전용으로 조회."""
    render_other_assets_dashboard(
        client,
        None,
        ownership_filter=ownership_filter,
        standalone=True,
    )


def view_holdings(
    client,
    live_rows,
    *,
    account_label: str,
    account_ids: list[str] | None,
    stats: dict,
) -> None:
    """보유: 선택한 계좌의 종목 리스트 + 총 수익률 + 매매/배당 이력."""
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

    export_df = pd.DataFrame(
        [
            {
                "티커": i["ticker"],
                "종목명": i.get("name") or i["ticker"],
                "수량": i["tot"].get("qty"),
                "평균단가": i["tot"].get("avg"),
                "현재가": i["tot"].get("price"),
                "평가금액": i["tot"].get("value"),
                "수익률(%)": i["tot"].get("return_%"),
                "통화": i["tot"].get("ccy"),
            }
            for i in items
        ]
    )
    download_csv_button(export_df, filename_prefix="holdings", key="export_holdings_csv")

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

    with st.expander("평가액 추이", expanded=False):
        months = period_radio(key="dash_period_holdings", default="1년")
        hdf = filter_by_period(_load_holding_snaps(client), months, date_col="snapshot_date")
        if not hdf.empty and "market_value_krw" in hdf.columns:
            one = hdf[hdf["ticker"] == pick]
            if account_label != "전체":
                ids = {r.get("account_id") for r in chosen["accounts"] if r.get("account_id")}
                if ids and "account_id" in one.columns:
                    one = one[one["account_id"].astype(str).isin(ids)]
            one = one.sort_values("snapshot_date")
            if not one.empty:
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
                    chart_layout(
                        220,
                        title=f"{title_name} 평가액",
                        yaxis_title="원",
                    )
                )
                show_plotly(fig)
            else:
                st.caption("이 종목의 추이 데이터가 없습니다.")
        else:
            st.caption("선택한 기간에 평가액 추이가 없습니다.")

    section_header("매매 · 배당 이력")
    render_ticker_history(client, pick, account_ids=account_ids)



def main() -> None:
    page_hero(
        "내 자산",
        "순자산을 한눈에. 계좌·소유 필터는 상단에 고정됩니다.",
        compact=True,
    )
    view = render_grouped_asset_nav(state_key="dash_view")

    user, client = require_auth()
    ensure_profile(user, client)

    account_label = "전체"
    account_ids = None
    ownership_filter = None
    if view not in ("세금", "관심"):
        account_label = render_account_selector(client)
        account_ids = account_ids_for_label(client, account_label)
        own_opts = ["전체"] + list(OWNERSHIP_KO.keys())
        own_pick = st.selectbox(
            "소유",
            own_opts,
            format_func=lambda k: "전체" if k == "전체" else OWNERSHIP_KO.get(k, k),
            key="dash_ownership_filter",
            help="공동/나/배우자로 순자산·보유를 좁혀 봅니다.",
        )
        ownership_filter = None if own_pick == "전체" else own_pick

    holdings = client.table("holdings").select("*").execute().data or []
    live_rows, _total_usd, _total_krw, total_debt, any_stale, usdkrw = _live_holdings(
        client, holdings
    )
    filtered = _filter_live_by_account_ids(live_rows, account_ids)
    if ownership_filter:
        amap = {str(a["id"]): a for a in load_accounts_enriched(client)}
        filtered = [
            r
            for r in filtered
            if (amap.get(str(r.get("account_id") or "")) or {}).get("ownership", "joint")
            == ownership_filter
        ]
    stats = _portfolio_stats(filtered, usdkrw)

    # Alerts (price + wealth)
    prior_net = None
    try:
        snaps = (
            client.table("daily_snapshots")
            .select("net_assets,snapshot_date")
            .order("snapshot_date", desc=True)
            .limit(2)
            .execute()
            .data
            or []
        )
        if len(snaps) >= 1:
            prior_net = float(snaps[0]["net_assets"])
    except Exception:
        prior_net = None

    nw_preview = compute_net_worth(
        filtered,
        accounts=load_accounts_enriched(client),
        other_assets=load_other_assets(client),
        total_debt=float(total_debt or 0) if account_ids is None else 0.0,
        usdkrw=usdkrw,
        account_ids=account_ids,
        ownership=ownership_filter,
    )
    try:
        evaluate_alerts(client, str(user.id))
        evaluate_wealth_alerts(
            client,
            str(user.id),
            live_net=nw_preview.get("net"),
            prior_net=prior_net,
            any_stale=any_stale,
        )
        if view not in ("관심",):
            render_alert_banners(client, str(user.id))
            render_wealth_alert_banners(client, str(user.id))
    except Exception:
        pass

    if view in ("홈", "보유", "손익", "배당", "거래", "순자산", "기타자산"):
        _status_bar(client, any_stale=any_stale)

    if view == "홈":
        view_home(
            client,
            filtered,
            total_debt if account_ids is None else 0.0,
            any_stale,
            account_label=account_label,
            account_ids=account_ids,
            stats=stats,
            usdkrw=usdkrw,
            ownership_filter=ownership_filter,
        )
    elif view == "순자산":
        view_networth_detail(
            client,
            filtered,
            total_debt if account_ids is None else 0.0,
            usdkrw=usdkrw,
            account_ids=account_ids,
            account_label=account_label,
        )
    elif view == "기타자산":
        view_other_assets(client, ownership_filter=ownership_filter)
    elif view == "보유":
        view_holdings(
            client,
            filtered,
            account_label=account_label,
            account_ids=account_ids,
            stats=stats,
        )
    elif view == "손익":
        render_total_realized_pnl(
            client,
            compact=False,
            account_ids=account_ids,
            account_label=account_label,
        )
    elif view == "배당":
        render_dividend_calendar(
            client,
            account_ids=account_ids,
            account_label=account_label,
            usdkrw=usdkrw,
        )
    elif view == "거래":
        render_flow_charts(
            client,
            account_ids=account_ids,
            account_label=account_label,
        )
    elif view == "관심":
        render_watchlist_panel(client, user)
    elif view == "부채":
        render_debt_dashboard(
            client,
            account_ids=account_ids,
            account_label=account_label,
        )
    else:
        render_tax_dashboard(client)


main()
