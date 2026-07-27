"""Wealth-level alerts: NW drop, debt due, monthly digest banners."""

from __future__ import annotations

from datetime import date, datetime, timezone

import streamlit as st

from lib.net_worth import debts_due_soon
from lib.ux import fmt_krw


def _safe_insert_alert(client, row: dict) -> None:
    try:
        # Deduplicate unacked same kind+title today
        existing = (
            client.table("wealth_alert_events")
            .select("id")
            .eq("user_id", row["user_id"])
            .eq("alert_kind", row["alert_kind"])
            .eq("acknowledged", False)
            .limit(5)
            .execute()
            .data
            or []
        )
        if existing and row["alert_kind"] != "monthly_digest":
            return
        if row["alert_kind"] == "monthly_digest" and existing:
            return
        client.table("wealth_alert_events").insert(row).execute()
    except Exception:
        pass


def evaluate_wealth_alerts(
    client,
    user_id: str,
    *,
    live_net: float | None,
    prior_net: float | None,
    any_stale: bool = False,
) -> None:
    """Create wealth_alert_events when conditions match (best-effort)."""
    # NW drop ≥ 3% vs prior snapshot
    if live_net is not None and prior_net is not None and abs(prior_net) > 1:
        change_pct = 100.0 * (live_net - prior_net) / prior_net
        if change_pct <= -3.0:
            _safe_insert_alert(
                client,
                {
                    "user_id": user_id,
                    "alert_kind": "nw_drop",
                    "title": f"순자산 {change_pct:.1f}% 하락",
                    "body": (
                        f"현재 {fmt_krw(live_net)} · 이전 {fmt_krw(prior_net)} "
                        f"({fmt_krw(live_net - prior_net, signed=True)})"
                    ),
                    "meta": {
                        "live_net": live_net,
                        "prior_net": prior_net,
                        "change_pct": change_pct,
                    },
                    "acknowledged": False,
                },
            )

    for d in debts_due_soon(client, within_days=30):
        _safe_insert_alert(
            client,
            {
                "user_id": user_id,
                "alert_kind": "debt_due",
                "title": f"부채 만기 임박 · {d.get('lender')}",
                "body": f"{d['_due'].isoformat()} ({d['_days']}일 후) · 잔금 {fmt_krw(d.get('principal'))}",
                "meta": {"debt_id": d.get("id"), "due_date": d["_due"].isoformat()},
                "acknowledged": False,
            },
        )

    if any_stale:
        _safe_insert_alert(
            client,
            {
                "user_id": user_id,
                "alert_kind": "stale_prices",
                "title": "시세 지연",
                "body": "일부 종목 시세가 오래되었습니다. 자산 챗에서 시세를 갱신하세요.",
                "meta": {},
                "acknowledged": False,
            },
        )

    # Monthly digest on the 1st–3rd
    today = date.today()
    if today.day <= 3:
        _safe_insert_alert(
            client,
            {
                "user_id": user_id,
                "alert_kind": "monthly_digest",
                "title": f"{today.month}월 자산 요약 확인",
                "body": "홈의 「이번 달 요약」에서 순자산 변화와 실현손익을 확인하세요.",
                "meta": {"month": today.isoformat()[:7]},
                "acknowledged": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )


def render_wealth_alert_banners(client, user_id: str) -> None:
    try:
        alerts = (
            client.table("wealth_alert_events")
            .select("*")
            .eq("user_id", user_id)
            .eq("acknowledged", False)
            .order("created_at", desc=True)
            .limit(8)
            .execute()
            .data
            or []
        )
    except Exception:
        # Fallback: ephemeral debt-due banners without persistence
        due = debts_due_soon(client, within_days=30)
        for d in due[:3]:
            st.warning(
                f"📅 부채 만기 · {d.get('lender')} · {d['_due'].isoformat()} "
                f"({d['_days']}일 후)"
            )
        return

    if not alerts:
        return
    for a in alerts[:5]:
        kind = a.get("alert_kind")
        icon = {
            "nw_drop": "📉",
            "debt_due": "📅",
            "monthly_digest": "🗓",
            "stale_prices": "⏰",
        }.get(kind, "🔔")
        st.warning(f"{icon} {a.get('title')} — {a.get('body') or ''}")
    if st.button("자산 알림 모두 확인", key="ack_wealth_alerts"):
        try:
            client.table("wealth_alert_events").update({"acknowledged": True}).eq(
                "user_id", user_id
            ).eq("acknowledged", False).execute()
            st.rerun()
        except Exception:
            st.error("알림 확인 처리에 실패했습니다.")


def render_monthly_summary(client, nw: dict, stats_month: dict) -> None:
    st.markdown("##### 이번 달 요약")
    c1, c2, c3 = st.columns(3)
    c1.metric("순자산", fmt_krw(nw.get("net")))
    change = stats_month.get("nw_change")
    c2.metric(
        "월초 대비",
        fmt_krw(change, signed=True) if change is not None else "—",
        delta=(
            f"{stats_month['nw_change_pct']:+.2f}%"
            if stats_month.get("nw_change_pct") is not None
            else None
        ),
        delta_color="inverse",
    )
    realized = stats_month.get("realized_month")
    c3.metric(
        "이달 실현손익",
        fmt_krw(realized, signed=True) if realized is not None else "—",
    )
    st.caption(
        "월초 대비 = 이번 달 1일 이전 스냅샷 대비 현재 순자산. "
        "실현손익은 매매·배당·이자 합산(가능한 경우)."
    )
