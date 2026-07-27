"""Home-tab insights: today/week P&L, allocation, benchmark, dividend calendar."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.theme import PRIMARY, chart_layout, show_plotly


def _fmt_money(v, currency: str = "KRW") -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        n = float(v)
    except (TypeError, ValueError):
        return "—"
    if currency == "USD":
        return f"${n:,.2f}"
    sign = "+" if n > 0 else ""
    return f"{sign}₩{n:,.0f}" if n != 0 else f"₩{n:,.0f}"


def _fmt_signed_pct(v: float | None) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    sign = "+" if v > 0.005 else ""
    return f"{sign}{v:.2f}%"


def _to_krw(amount: float | None, ccy: str, usdkrw: float | None) -> float | None:
    if amount is None:
        return None
    if (ccy or "KRW") == "USD":
        return float(amount) * usdkrw if usdkrw else None
    return float(amount)


def market_region(ticker: str | None, ccy: str | None) -> str:
    t = str(ticker or "").strip()
    if t.isdigit() and len(t) == 6:
        return "국내"
    if (ccy or "").upper() == "KRW":
        return "국내"
    return "해외"


# ---------------------------------------------------------------------------
# Period change (오늘 / 이번 주)
# ---------------------------------------------------------------------------


def load_holding_snaps(client, days: int = 40) -> pd.DataFrame:
    since = (date.today() - timedelta(days=days)).isoformat()
    rows = (
        client.table("holding_daily_snapshots")
        .select(
            "snapshot_date,account_id,ticker,quantity,avg_price,price,"
            "currency,market_value,market_value_krw"
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
    for col in ("quantity", "avg_price", "price", "market_value", "market_value_krw"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _sum_value_on_date(
    hdf: pd.DataFrame, on: date, account_ids: list[str] | None
) -> float | None:
    if hdf.empty:
        return None
    part = hdf[hdf["snapshot_date"] == on]
    if account_ids is not None and "account_id" in part.columns:
        allow = {str(a) for a in account_ids}
        part = part[part["account_id"].astype(str).isin(allow)]
    if part.empty or "market_value_krw" not in part.columns:
        return None
    total = float(part["market_value_krw"].sum(skipna=True))
    return total if part["market_value_krw"].notna().any() else None


def _nearest_prior_date(dates: list[date], before: date) -> date | None:
    prior = [d for d in dates if d < before]
    return max(prior) if prior else None


def period_change_stats(
    client,
    live_value_krw: float | None,
    account_ids: list[str] | None,
) -> dict[str, float | None]:
    """Compare live valuation vs prior snapshot days (1d / ~7d)."""
    hdf = load_holding_snaps(client, days=40)
    today = date.today()
    out: dict[str, float | None] = {
        "today_pnl": None,
        "today_pct": None,
        "week_pnl": None,
        "week_pct": None,
        "ref_1d": None,
        "ref_7d": None,
    }
    if live_value_krw is None:
        return out

    dates = sorted(hdf["snapshot_date"].unique().tolist()) if not hdf.empty else []
    # Prefer yesterday; else nearest prior snapshot
    d1 = today - timedelta(days=1)
    if d1 not in dates:
        d1 = _nearest_prior_date(dates, today)  # type: ignore[assignment]
    d7_target = today - timedelta(days=7)
    d7 = d7_target if d7_target in dates else _nearest_prior_date(dates, d7_target + timedelta(days=1))

    if d1:
        v1 = _sum_value_on_date(hdf, d1, account_ids)
        out["ref_1d"] = v1
        if v1 is not None:
            out["today_pnl"] = live_value_krw - v1
            out["today_pct"] = (out["today_pnl"] / v1 * 100.0) if v1 else None
    if d7:
        v7 = _sum_value_on_date(hdf, d7, account_ids)
        out["ref_7d"] = v7
        if v7 is not None:
            out["week_pnl"] = live_value_krw - v7
            out["week_pct"] = (out["week_pnl"] / v7 * 100.0) if v7 else None
    return out


def render_period_change_row(stats: dict[str, float | None]) -> None:
    from lib.ux import fmt_krw

    c1, c2 = st.columns(2, gap="small")
    with c1:
        st.metric(
            "오늘 손익",
            fmt_krw(stats.get("today_pnl"), signed=True)
            if stats.get("today_pnl") is not None
            else "—",
            delta=_fmt_signed_pct(stats.get("today_pct"))
            if stats.get("today_pct") is not None
            else None,
            delta_color="inverse",
        )
    with c2:
        st.metric(
            "이번 주 손익",
            fmt_krw(stats.get("week_pnl"), signed=True)
            if stats.get("week_pnl") is not None
            else "—",
            delta=_fmt_signed_pct(stats.get("week_pct"))
            if stats.get("week_pct") is not None
            else None,
            delta_color="inverse",
        )
    if stats.get("today_pnl") is None and stats.get("week_pnl") is None:
        from lib.ux import empty_cta

        empty_cta(
            "스냅샷이 쌓이면 오늘·주간 손익이 표시됩니다.",
            button_label="자산 챗으로 이동",
            page_title="자산 챗",
            key="cta_period_change",
        )


# ---------------------------------------------------------------------------
# Unrealized vs realized
# ---------------------------------------------------------------------------


def realized_pnl_ytd_krw(client, account_ids: list[str] | None) -> float | None:
    from lib.realized_pnl_ui import load_total_realized

    df = load_total_realized(client, account_ids=account_ids)
    if df.empty or "pnl_krw" not in df.columns:
        return None
    year = date.today().year
    part = df[df["event_date"].dt.year == year]
    if part.empty or part["pnl_krw"].isna().all():
        return None
    return float(part["pnl_krw"].sum(skipna=True))


def render_pnl_split(
    *,
    unrealized: float | None,
    realized_ytd: float | None,
) -> None:
    from lib.ux import fmt_krw

    c1, c2 = st.columns(2, gap="small")
    c1.metric(
        "미실현 손익",
        fmt_krw(unrealized, signed=True) if unrealized is not None else "—",
    )
    c2.metric(
        "실현 손익 (올해)",
        fmt_krw(realized_ytd, signed=True) if realized_ytd is not None else "—",
    )
    st.caption("미실현 = 평가액 − 매입원금 · 실현 = 올해 매도·배당·이자 합계")


# ---------------------------------------------------------------------------
# Asset allocation (treemap heat map)
# ---------------------------------------------------------------------------

# US-style: up=green, down=red (midpoint near ink for flat returns)
_TREEMAP_COLORSCALE = [
    [0.0, "#E11D48"],
    [0.5, "#1F2937"],
    [1.0, "#03C75A"],
]


def _treemap_display_label(name: str, ticker: str, max_chars: int = 10) -> str:
    """Short label so small tiles still show a readable name."""
    n = str(name or "").strip()
    t = str(ticker or "").strip()
    if not n or n.upper() == t.upper():
        return t or "?"
    if len(n) <= max_chars:
        return n
    # Prefer ticker when the company name is too long for the tile
    if t and len(t) <= max_chars:
        return t
    return n[: max_chars - 1] + "…"


def allocation_frames(
    live_rows: list[dict], usdkrw: float | None
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (by_ticker, by_region, by_account) with value_krw (tests + legacy)."""
    leaves = allocation_leaves(live_rows, usdkrw)
    if leaves.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    by_t = (
        leaves.groupby(["ticker", "label"], as_index=False)
        .agg(value_krw=("value_krw", "sum"), return_pct=("return_pct", "mean"))
        .sort_values("value_krw", ascending=False)
    )
    by_r = (
        leaves.groupby("region", as_index=False)["value_krw"]
        .sum()
        .rename(columns={"region": "label"})
        .sort_values("value_krw", ascending=False)
    )
    by_a = (
        leaves.groupby("account", as_index=False)["value_krw"]
        .sum()
        .rename(columns={"account": "label"})
        .sort_values("value_krw", ascending=False)
    )
    return by_t, by_r, by_a


def allocation_leaves(live_rows: list[dict], usdkrw: float | None) -> pd.DataFrame:
    """One row per holding line with KRW value + return % for treemap."""
    rows: list[dict] = []
    for r in live_rows:
        v = _to_krw(
            float(r["value"]) if r.get("value") is not None else None,
            r.get("ccy") or "USD",
            usdkrw,
        )
        if v is None or v <= 0:
            continue
        ticker = str(r.get("ticker") or "?").strip() or "?"
        name = str(r.get("name") or ticker).strip() or ticker
        ret = r.get("return_%")
        try:
            ret_f = float(ret) if ret is not None else None
        except (TypeError, ValueError):
            ret_f = None
        rows.append(
            {
                "ticker": ticker,
                "label": name,
                "region": market_region(ticker, r.get("ccy")),
                "account": r.get("institution") or "계좌",
                "value_krw": float(v),
                "return_pct": ret_f if ret_f is not None else 0.0,
                "has_return": ret_f is not None,
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _treemap(df: pd.DataFrame, path_cols: list[str], title: str) -> None:
    """Plotly treemap: size=value_krw, color=return_pct. Single-dict layout only."""
    if df is None or df.empty:
        st.caption(f"{title}: 표시할 데이터가 없습니다.")
        return

    work = df.copy()
    work["value_krw"] = pd.to_numeric(work["value_krw"], errors="coerce").fillna(0.0)
    work = work[work["value_krw"] > 0]
    if work.empty:
        st.caption(f"{title}: 표시할 데이터가 없습니다.")
        return

    work["return_pct"] = pd.to_numeric(work.get("return_pct"), errors="coerce").fillna(0.0)
    work["ret_label"] = work["return_pct"].map(lambda x: f"{x:+.1f}%")
    if "ticker" not in work.columns:
        work["ticker"] = work.get("label", pd.Series(["?"] * len(work))).astype(str)
    work["root"] = "전체"

    # Leaf path col → short display label; keep full name for hover
    leaf_col = path_cols[-1]
    for col in path_cols:
        if col not in work.columns:
            st.caption(f"{title}: 데이터 컬럼 오류 ({col})")
            return
        work[col] = work[col].astype(str).replace({"": "?", "nan": "?"})

    work["_full_name"] = work[leaf_col]
    work[leaf_col] = [
        _treemap_display_label(n, t)
        for n, t in zip(work["_full_name"], work["ticker"].astype(str), strict=False)
    ]

    path = ["root"] + path_cols

    try:
        import plotly.express as px
    except ImportError:
        st.error("plotly.express를 불러올 수 없습니다.")
        return

    fig = px.treemap(
        work,
        path=path,
        values="value_krw",
        color="return_pct",
        color_continuous_scale=_TREEMAP_COLORSCALE,
        color_continuous_midpoint=0,
        custom_data=["ret_label", "ticker", "value_krw", "_full_name"],
        hover_data={"return_pct": ":.2f", "value_krw": ":,.0f"},
    )
    fig.update_traces(
        texttemplate="%{label}<br>%{customdata[0]}",
        textposition="middle center",
        textfont=dict(size=11, color="#F8FAFC"),
        root_color="rgba(0,0,0,0)",
        hovertemplate=(
            "<b>%{customdata[3]}</b><br>"
            "평가 ₩%{customdata[2]:,.0f}<br>"
            "수익률 %{customdata[0]}"
            "<extra></extra>"
        ),
        marker=dict(line=dict(width=1.5, color="#0B1220")),
        pathbar=dict(visible=False),
    )
    # One dict only — never **chart_layout(..., legend=...) style collisions
    layout = chart_layout(
        400,
        title=title,
        margin=dict(l=4, r=4, t=48, b=8),
        coloraxis_showscale=False,
    )
    # Force labels on small tiles (mode=hide was blanking most rectangles)
    layout["uniformtext"] = dict(minsize=8, mode="show")
    fig.update_layout(layout)
    show_plotly(fig)
    st.caption("사각형 크기 = 평가액 비중 · 색 = 수익률 (상승 초록 / 하락 빨강)")


def render_allocation(live_rows: list[dict], usdkrw: float | None) -> None:
    leaves = allocation_leaves(live_rows, usdkrw)
    if leaves.empty:
        st.info("배분 차트를 그리려면 시세가 있는 보유가 필요합니다.")
        return
    mode = st.radio(
        "배분 기준",
        ["종목", "국내/해외", "계좌"],
        horizontal=True,
        key="alloc_mode",
    )
    if mode == "종목":
        # Aggregate same ticker across accounts
        by_t = (
            leaves.groupby(["ticker", "label"], as_index=False)
            .agg(
                value_krw=("value_krw", "sum"),
                return_pct=("return_pct", "mean"),
            )
        )
        _treemap(by_t, ["label"], "종목 비중")
    elif mode == "국내/해외":
        by_r = (
            leaves.groupby(["region", "ticker", "label"], as_index=False)
            .agg(
                value_krw=("value_krw", "sum"),
                return_pct=("return_pct", "mean"),
            )
        )
        _treemap(by_r, ["region", "label"], "국내·해외 비중")
    else:
        _treemap(leaves, ["account", "label"], "계좌 비중")


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------


def load_index_snaps(client, days: int = 400) -> pd.DataFrame:
    """Load index snapshots. Tolerates DBs that have not applied migration 0016 (kospi)."""
    since = (date.today() - timedelta(days=days)).isoformat()
    rows: list[dict] = []
    try:
        rows = (
            client.table("market_index_snapshots")
            .select("snapshot_date,nasdaq,sp500,kospi,usdkrw")
            .gte("snapshot_date", since)
            .order("snapshot_date")
            .execute()
            .data
            or []
        )
    except Exception:
        # Column `kospi` missing until migration 0016 is applied
        try:
            rows = (
                client.table("market_index_snapshots")
                .select("snapshot_date,nasdaq,sp500,usdkrw")
                .gte("snapshot_date", since)
                .order("snapshot_date")
                .execute()
                .data
                or []
            )
        except Exception:
            return pd.DataFrame()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"]).dt.date
    for col in ("nasdaq", "sp500", "kospi", "usdkrw"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_portfolio_series(
    client, account_ids: list[str] | None, days: int = 400
) -> pd.DataFrame:
    """Daily portfolio market value (KRW) from holding snapshots or daily_snapshots."""
    if account_ids is None:
        since = (date.today() - timedelta(days=days)).isoformat()
        rows = (
            client.table("daily_snapshots")
            .select("snapshot_date,total_investment,net_assets")
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
        df["value_krw"] = pd.to_numeric(df["total_investment"], errors="coerce")
        return df[["snapshot_date", "value_krw"]].dropna()

    hdf = load_holding_snaps(client, days=days)
    if hdf.empty:
        return pd.DataFrame()
    allow = {str(a) for a in account_ids}
    hdf = hdf[hdf["account_id"].astype(str).isin(allow)]
    if hdf.empty:
        return pd.DataFrame()
    summed = (
        hdf.groupby("snapshot_date", as_index=False)["market_value_krw"]
        .sum()
        .rename(columns={"market_value_krw": "value_krw"})
    )
    return summed.dropna()


def render_benchmark_chart(
    client,
    account_ids: list[str] | None,
    *,
    months: int | None,
) -> None:
    from lib.chart_period import filter_by_period

    port = filter_by_period(
        load_portfolio_series(client, account_ids), months, date_col="snapshot_date"
    )
    try:
        idx = filter_by_period(load_index_snaps(client), months, date_col="snapshot_date")
    except Exception:
        idx = pd.DataFrame()
        st.caption("지수 스냅샷을 불러오지 못했습니다. migration 0016 적용 여부를 확인하세요.")

    if port.empty:
        st.info("벤치마크 비교용 포트폴리오 스냅샷이 없습니다.")
        return

    options = ["S&P 500", "NASDAQ"]
    if not idx.empty and "kospi" in idx.columns:
        options.append("KOSPI")
    elif idx.empty or "kospi" not in idx.columns:
        st.caption("KOSPI는 migration 0016 적용 + 시세 갱신 후 비교할 수 있습니다.")

    bench = st.selectbox("비교 지수", options, key="bench_index")
    col_map = {"S&P 500": "sp500", "NASDAQ": "nasdaq", "KOSPI": "kospi"}
    col = col_map[bench]

    fig = go.Figure()
    p0 = float(port.iloc[0]["value_krw"])
    if p0 and p0 > 0:
        fig.add_trace(
            go.Scatter(
                x=port["snapshot_date"],
                y=(port["value_krw"] / p0) * 100.0,
                name="내 포트폴리오",
                mode="lines",
                line=dict(color=PRIMARY, width=2.5),
            )
        )

    if not idx.empty and col in idx.columns and idx[col].notna().any():
        merged = pd.merge(
            port[["snapshot_date"]],
            idx[["snapshot_date", col]],
            on="snapshot_date",
            how="inner",
        ).dropna()
        if not merged.empty:
            i0 = float(merged.iloc[0][col])
            if i0 and i0 > 0:
                fig.add_trace(
                    go.Scatter(
                        x=merged["snapshot_date"],
                        y=(merged[col] / i0) * 100.0,
                        name=bench,
                        mode="lines",
                        line=dict(color="#94A3B8", width=2, dash="dot"),
                    )
                )
        else:
            st.caption(f"{bench} 지수 데이터가 아직 부족합니다. 시세 갱신 시 함께 저장됩니다.")
    else:
        st.caption(f"{bench} 지수 데이터가 없습니다. 「자산 챗」에서 시세를 갱신하세요.")

    if not fig.data:
        return
    fig.update_layout(
        chart_layout(
            260,
            title=f"수익률 비교 (시작=100) · {bench}",
            yaxis_title="지수화",
        )
    )
    show_plotly(fig)


# ---------------------------------------------------------------------------
# Dividend calendar
# ---------------------------------------------------------------------------


def load_dividends(client, account_ids: list[str] | None = None) -> pd.DataFrame:
    rows = (
        client.table("dividends")
        .select("id,pay_date,ticker,name,amount,currency,account_id,memo")
        .order("pay_date", desc=True)
        .limit(500)
        .execute()
        .data
        or []
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if account_ids is not None:
        allow = {str(a) for a in account_ids}
        df = df[df["account_id"].astype(str).isin(allow)]
    if df.empty:
        return df
    df["pay_date"] = pd.to_datetime(df["pay_date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    return df


def dividend_stats(df: pd.DataFrame, usdkrw: float | None) -> dict[str, Any]:
    if df.empty:
        return {"month_krw": 0.0, "ytd_krw": 0.0, "avg_month_krw": 0.0, "expected_krw": 0.0}

    def to_krw(row) -> float:
        amt = float(row["amount"] or 0)
        if str(row.get("currency") or "KRW").upper() == "USD":
            return amt * float(usdkrw) if usdkrw else 0.0
        return amt

    work = df.dropna(subset=["pay_date"]).copy()
    work["krw"] = work.apply(to_krw, axis=1)
    today = date.today()
    this_month = work[
        (work["pay_date"].dt.year == today.year)
        & (work["pay_date"].dt.month == today.month)
    ]
    ytd = work[work["pay_date"].dt.year == today.year]
    # last 12 months monthly average as expected
    since = pd.Timestamp(today - timedelta(days=365))
    last12 = work[work["pay_date"] >= since]
    if not last12.empty:
        last12 = last12.copy()
        last12["ym"] = last12["pay_date"].dt.to_period("M")
        monthly = last12.groupby("ym")["krw"].sum()
        avg = float(monthly.mean()) if len(monthly) else 0.0
    else:
        avg = 0.0
    return {
        "month_krw": float(this_month["krw"].sum()) if not this_month.empty else 0.0,
        "ytd_krw": float(ytd["krw"].sum()) if not ytd.empty else 0.0,
        "avg_month_krw": avg,
        "expected_krw": avg,  # simple expectation = trailing avg
    }


def render_dividend_calendar(
    client,
    *,
    account_ids: list[str] | None,
    account_label: str,
    usdkrw: float | None,
) -> None:
    df = load_dividends(client, account_ids)
    label = f"{account_label} · " if account_label and account_label != "전체" else ""
    if df.empty:
        from lib.ux import empty_cta, section_header

        section_header("배당")
        empty_cta(
            f"{label}배당 기록이 없습니다. OCR·수기로 배당을 등록하세요.",
            button_label="기록하기로 이동",
            page_title="기록하기",
            key="cta_div_empty",
        )
        return

    stats = dividend_stats(df, usdkrw)
    m1, m2, m3 = st.columns(3, gap="small")
    m1.metric("이번 달 배당", _fmt_money(stats["month_krw"], "KRW"))
    m2.metric("올해 배당", _fmt_money(stats["ytd_krw"], "KRW"))
    m3.metric("예상 월 배당", _fmt_money(stats["expected_krw"], "KRW"))
    st.caption("예상 월 배당 = 최근 12개월 월평균 배당(단순 추정)")

    work = df.dropna(subset=["pay_date"]).copy()
    work["월"] = work["pay_date"].dt.to_period("M").astype(str)
    work["krw"] = work.apply(
        lambda r: float(r["amount"] or 0)
        * (float(usdkrw) if str(r.get("currency") or "").upper() == "USD" and usdkrw else 1.0)
        if str(r.get("currency") or "KRW").upper() == "USD"
        else float(r["amount"] or 0),
        axis=1,
    )
    monthly = (
        work.groupby("월", as_index=False)["krw"].sum().sort_values("월").tail(18)
    )
    if not monthly.empty:
        fig = go.Figure(
            go.Bar(
                x=monthly["월"],
                y=monthly["krw"],
                marker_color=PRIMARY,
                name="배당",
            )
        )
        fig.update_layout(
            chart_layout(
                240,
                title="월별 배당 수입",
                yaxis_title="원",
                showlegend=False,
            )
        )
        show_plotly(fig)

    # Calendar-ish list for current + next month
    today = date.today()
    next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    window = work[
        (
            (work["pay_date"].dt.year == today.year)
            & (work["pay_date"].dt.month == today.month)
        )
        | (
            (work["pay_date"].dt.year == next_month.year)
            & (work["pay_date"].dt.month == next_month.month)
        )
    ].sort_values("pay_date")

    st.markdown("##### 이번·다음 달 배당 일정")
    if window.empty:
        st.caption("이번·다음 달에 기록된 배당이 없습니다.")
    else:
        cal = pd.DataFrame(
            {
                "지급일": window["pay_date"].dt.strftime("%Y-%m-%d"),
                "종목": window.apply(
                    lambda r: r["name"]
                    if r.get("name") and r["name"] != r.get("ticker")
                    else r.get("ticker"),
                    axis=1,
                ),
                "티커": window["ticker"],
                "금액": window.apply(
                    lambda r: _fmt_money(r["amount"], r.get("currency") or "KRW").lstrip("+"),
                    axis=1,
                ),
                "메모": window["memo"].fillna("") if "memo" in window.columns else "",
            }
        )
        st.dataframe(cal, use_container_width=True, hide_index=True)

    st.markdown("##### 최근 배당 내역")
    recent = work.sort_values("pay_date", ascending=False).head(50)
    hist = pd.DataFrame(
        {
            "지급일": recent["pay_date"].dt.strftime("%Y-%m-%d"),
            "종목": recent.apply(
                lambda r: r["name"]
                if r.get("name") and r["name"] != r.get("ticker")
                else r.get("ticker"),
                axis=1,
            ),
            "티커": recent["ticker"],
            "금액": recent["amount"],
            "통화": recent["currency"],
        }
    )
    st.dataframe(hist, use_container_width=True, hide_index=True, height=320)

    from lib.export_csv import download_csv_button

    download_csv_button(hist, filename_prefix="dividends", key="export_div_csv")
