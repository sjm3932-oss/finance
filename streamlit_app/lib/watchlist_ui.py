"""관심종목 + 목표가/손절가 알림 UI."""

from __future__ import annotations

from typing import Any

import streamlit as st

from lib.market_data import fetch_price, is_korean_ticker, normalize_ticker


def _price_label(price: float | None, ticker: str, ccy: str | None) -> str:
    if price is None:
        return "—"
    use_krw = (ccy or "").upper() == "KRW" or is_korean_ticker(ticker)
    return f"₩{price:,.0f}" if use_krw else f"${price:,.2f}"


def load_watchlist(client, user_id: str) -> list[dict]:
    try:
        return (
            client.table("watchlist")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def load_unacked_alerts(client, user_id: str, limit: int = 20) -> list[dict]:
    try:
        return (
            client.table("price_alert_events")
            .select("*")
            .eq("user_id", user_id)
            .eq("acknowledged", False)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def evaluate_alerts(client, user_id: str) -> list[dict]:
    """Compare watchlist thresholds to market_prices; insert new alert events."""
    items = load_watchlist(client, user_id)
    if not items:
        return []
    prices = {
        p["ticker"]: p
        for p in (client.table("market_prices").select("*").execute().data or [])
    }
    created: list[dict] = []
    for w in items:
        ticker = normalize_ticker(w.get("ticker"))
        mp = prices.get(ticker)
        if not mp or mp.get("price") is None:
            continue
        price = float(mp["price"])
        target = w.get("target_price")
        stop = w.get("stop_price")
        kinds: list[tuple[str, float]] = []
        if target is not None and price >= float(target):
            kinds.append(("target", float(target)))
        if stop is not None and price <= float(stop):
            kinds.append(("stop", float(stop)))
        for kind, trigger in kinds:
            # Avoid flooding: skip if an unacked alert of same kind exists
            existing = (
                client.table("price_alert_events")
                .select("id")
                .eq("user_id", user_id)
                .eq("ticker", ticker)
                .eq("alert_kind", kind)
                .eq("acknowledged", False)
                .limit(1)
                .execute()
                .data
                or []
            )
            if existing:
                continue
            row = {
                "user_id": user_id,
                "watchlist_id": w.get("id"),
                "ticker": ticker,
                "alert_kind": kind,
                "trigger_price": trigger,
                "market_price": price,
                "acknowledged": False,
            }
            try:
                ins = client.table("price_alert_events").insert(row).execute().data or []
                if ins:
                    created.append(ins[0])
            except Exception:
                continue
    return created


def render_alert_banners(client, user_id: str) -> None:
    alerts = load_unacked_alerts(client, user_id)
    if not alerts:
        return
    for a in alerts[:5]:
        kind = "목표가 도달" if a.get("alert_kind") == "target" else "손절가 도달"
        st.warning(
            f"🔔 {a.get('ticker')} · {kind} "
            f"(기준 {a.get('trigger_price')} / 현재 {a.get('market_price')})"
        )
    if st.button("알림 모두 확인", key="ack_all_alerts"):
        try:
            client.table("price_alert_events").update({"acknowledged": True}).eq(
                "user_id", user_id
            ).eq("acknowledged", False).execute()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def render_watchlist_panel(client, user) -> None:
    """Full watchlist CRUD + alert check."""
    user_id = str(user.id)
    st.caption("관심종목을 등록하고 목표가·손절가에 도달하면 알림이 쌓입니다.")

    # Ensure migration applied
    try:
        client.table("watchlist").select("id").limit(1).execute()
    except Exception:
        st.error(
            "watchlist 테이블이 없습니다. Supabase에 migration 0016을 적용하세요."
        )
        return

    render_alert_banners(client, user_id)

    with st.form("watch_add_form"):
        c1, c2 = st.columns(2)
        ticker = c1.text_input("티커", placeholder="005930 또는 AAPL").strip().upper()
        name = c2.text_input("종목명 (선택)", "")
        c3, c4 = st.columns(2)
        target = c3.number_input("목표가 (선택)", min_value=0.0, value=0.0, step=0.01, format="%.4f")
        stop = c4.number_input("손절가 (선택)", min_value=0.0, value=0.0, step=0.01, format="%.4f")
        note = st.text_input("메모", "")
        if st.form_submit_button("관심종목 추가", type="primary"):
            if not ticker:
                st.error("티커를 입력하세요.")
            else:
                resolved_name = name
                if not resolved_name:
                    try:
                        quote = fetch_price(ticker)
                        resolved_name = quote.get("name") or ticker
                        # also upsert price
                        client.table("market_prices").upsert(
                            {
                                "ticker": quote["ticker"],
                                "price": quote["price"],
                                "currency": quote["currency"],
                                "updated_at": quote["updated_at"],
                            }
                        ).execute()
                    except Exception:
                        resolved_name = ticker
                try:
                    client.table("watchlist").upsert(
                        {
                            "user_id": user_id,
                            "ticker": normalize_ticker(ticker),
                            "name": resolved_name,
                            "target_price": target if target > 0 else None,
                            "stop_price": stop if stop > 0 else None,
                            "note": note or None,
                        },
                        on_conflict="user_id,ticker",
                    ).execute()
                    st.success(f"{ticker} 등록됨")
                    st.rerun()
                except Exception as exc:
                    st.error(f"등록 실패: {exc}")

    if st.button("목표가·손절가 지금 검사", key="eval_alerts_btn"):
        n = evaluate_alerts(client, user_id)
        st.success(f"새 알림 {len(n)}건" if n else "조건에 해당하는 새 알림 없음")
        if n:
            st.rerun()

    items = load_watchlist(client, user_id)
    prices = {
        p["ticker"]: p
        for p in (client.table("market_prices").select("*").execute().data or [])
    }
    if not items:
        st.info("등록된 관심종목이 없습니다.")
        return

    for w in items:
        ticker = w.get("ticker") or ""
        mp = prices.get(ticker) or {}
        price = mp.get("price")
        ccy = mp.get("currency") or ("KRW" if is_korean_ticker(ticker) else "USD")
        name = w.get("name") or ticker
        cols = st.columns([2.2, 1.2, 1.2, 1.2, 0.7])
        cols[0].markdown(f"**{name}**  \n`{ticker}`")
        cols[1].markdown(f"현재  \n{_price_label(float(price) if price is not None else None, ticker, ccy)}")
        tgt = w.get("target_price")
        stp = w.get("stop_price")
        cols[2].markdown(f"목표  \n{_price_label(float(tgt) if tgt is not None else None, ticker, ccy)}")
        cols[3].markdown(f"손절  \n{_price_label(float(stp) if stp is not None else None, ticker, ccy)}")
        if cols[4].button("삭제", key=f"del_watch_{w['id']}"):
            client.table("watchlist").delete().eq("id", w["id"]).execute()
            st.rerun()
        if w.get("note"):
            st.caption(w["note"])
        st.divider()
