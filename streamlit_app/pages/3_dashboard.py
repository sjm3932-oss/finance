"""Page: Portfolio dashboard (v_portfolio + market_prices)."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

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
  .block-container { padding-top: 1rem; max-width: 960px; }
  div.stButton > button { width: 100%; min-height: 2.8rem; }
</style>
""",
    unsafe_allow_html=True,
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


def main() -> None:
    st.title("Dashboard")
    st.caption("순자산 · 수익률 · 시세 상태")

    user, client = require_auth()
    ensure_profile(user, client)

    holdings = client.table("holdings").select("*").execute().data or []
    tickers = sorted({h["ticker"] for h in holdings})

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("시세 새로고침", type="primary"):
            with st.spinner("Yahoo / Frankfurter 조회 중…"):
                rows, errors = refresh_tickers(tickers)
                # Prefer user client; fall back to service for upsert reliability
                writer = client
                try:
                    if rows:
                        writer.table("market_prices").upsert(rows, on_conflict="ticker").execute()
                except Exception:
                    writer = get_service_client()
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
                    st.success(f"갱신 {len(rows)}종 · USD/KRW {usdkrw:,.2f}")
                except Exception as exc:
                    st.warning(f"가격 일부 갱신, 환율 실패: {exc}")
                for e in errors:
                    st.caption(f"⚠ {e}")
            st.rerun()
    with col_b:
        st.caption(f"시세 {STALE_HOURS:.0f}시간 이상 오래되면 「시세 지연」 표시")

    prices = {
        p["ticker"]: p
        for p in (client.table("market_prices").select("*").execute().data or [])
    }
    usdkrw_row = prices.get("USDKRW")
    usdkrw = float(usdkrw_row["price"]) if usdkrw_row else None

    portfolio = client.table("v_portfolio").select("*").execute().data or []
    # Enrich with stale flag / KRW value
    rows_out = []
    total_usd = 0.0
    total_krw = 0.0
    cost_usd = 0.0
    any_stale = False
    missing_price = False

    by_ticker = {r["ticker"]: r for r in portfolio}
    # Include holdings even if view join missed
    for h in holdings:
        p = by_ticker.get(h["ticker"]) or {
            "ticker": h["ticker"],
            "name": h.get("name"),
            "quantity": h.get("quantity"),
            "avg_price": h.get("avg_price"),
            "current_price": None,
            "return_rate": None,
            "market_value": None,
            "account_id": h.get("account_id"),
        }
        mp = prices.get(h["ticker"])
        stale = is_stale(mp.get("updated_at") if mp else None)
        if stale:
            any_stale = True
        price = p.get("current_price")
        if price is None and mp:
            price = mp.get("price")
        qty = float(h.get("quantity") or 0)
        avg = float(h.get("avg_price") or 0)
        cur = (h.get("currency") or mp.get("currency") if mp else "USD") or "USD"
        mv = float(price) * qty if price is not None else None
        if mv is None:
            missing_price = True
        else:
            if cur == "USD":
                total_usd += mv
                if usdkrw:
                    total_krw += mv * usdkrw
            else:
                total_krw += mv
                if usdkrw:
                    total_usd += mv / usdkrw
        cost_usd += avg * qty
        ret = None
        if price is not None and avg:
            ret = (float(price) - avg) / avg * 100
        rows_out.append(
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

    if usdkrw:
        st.caption(f"USD/KRW {usdkrw:,.2f}" + (" · 시세 지연" if is_stale(usdkrw_row.get("updated_at")) else ""))
    if any_stale:
        st.warning("일부 시세가 지연되었습니다. 「시세 새로고침」을 눌러 주세요.")
    if missing_price:
        st.info("가격이 없는 종목(비상장 등)은 합산에서 제외됩니다.")

    st.subheader("보유 종목")
    st.dataframe(rows_out, use_container_width=True, hide_index=True)

    if cost_usd and total_usd:
        st.caption(f"평균단가 기준 원가(USD) ≈ {_fmt_money(cost_usd, 'USD')} · 평가 ≈ {_fmt_money(total_usd, 'USD')}")


main()
