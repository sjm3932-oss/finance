"""Shared UX helpers: money format, empty CTAs, job feedback, badges."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st

from lib.market_data import STALE_HOURS, is_stale

# Korean market convention: up=red, down=blue
COLOR_UP = "#E11D48"
COLOR_DOWN = "#2563EB"
COLOR_FLAT = "#6B7280"


def abbreviate_enabled() -> bool:
    return bool(st.session_state.get("ux_abbrev_money", False))


def render_abbrev_toggle(*, key: str = "ux_abbrev_money") -> bool:
    return st.toggle("금액 축약 (억·만)", key=key, help="큰 금액을 1.2억 / 340만처럼 짧게 표시")


def fmt_krw(
    v: float | int | None,
    *,
    signed: bool = False,
    abbreviate: bool | None = None,
) -> str:
    if v is None:
        return "—"
    try:
        n = float(v)
    except (TypeError, ValueError):
        return "—"
    use_abbr = abbreviate_enabled() if abbreviate is None else abbreviate
    sign = ""
    if signed:
        if n > 0:
            sign = "+"
        elif n < 0:
            sign = "-"
        abs_n = abs(n)
    else:
        abs_n = n
        if n < 0:
            sign = "-"
            abs_n = abs(n)

    if use_abbr:
        if abs_n >= 100_000_000:
            body = f"{abs_n / 100_000_000:.2f}".rstrip("0").rstrip(".") + "억"
        elif abs_n >= 10_000:
            body = f"{abs_n / 10_000:.1f}".rstrip("0").rstrip(".") + "만"
        else:
            body = f"{abs_n:,.0f}"
        return f"{sign}₩{body}" if sign != "-" else f"-₩{body}"
    # full
    if signed and n > 0:
        return f"+₩{abs_n:,.0f}"
    if n < 0 or sign == "-":
        return f"-₩{abs_n:,.0f}"
    return f"₩{abs_n:,.0f}"


def fmt_usd(v: float | None, *, signed: bool = False) -> str:
    if v is None:
        return "—"
    try:
        n = float(v)
    except (TypeError, ValueError):
        return "—"
    if signed and n > 0:
        return f"+${n:,.2f}"
    if n < 0:
        return f"-${abs(n):,.2f}"
    return f"${n:,.2f}"


def fmt_money(v, currency: str = "KRW", *, signed: bool = False) -> str:
    if (currency or "KRW").upper() == "USD":
        return fmt_usd(v if isinstance(v, (int, float)) else None, signed=signed)
    return fmt_krw(v, signed=signed)


def ret_class(ret: float | None) -> str:
    if ret is None:
        return "flat"
    if ret > 0.05:
        return "up"
    if ret < -0.05:
        return "down"
    return "flat"


def show_job_result(
    result: dict[str, Any],
    *,
    ok_msg: str,
    fail_msg: str = "작업에 실패했습니다.",
) -> bool:
    """Friendly success/error instead of raw st.json. Returns True if OK."""
    try:
        status = int(result.get("status") or 0)
    except (TypeError, ValueError):
        status = 0
    body = result.get("body")
    ok = 200 <= status < 300
    # Some gateways return 200 with ok:false
    if isinstance(body, dict) and body.get("ok") is False:
        ok = False
    if ok:
        st.success(ok_msg)
        if body is not None:
            with st.expander("상세 응답", expanded=False):
                st.write(body)
        return True
    st.error(fail_msg)
    with st.expander("오류 상세", expanded=True):
        st.write(body if body is not None else result)
    return False


def pending_ocr_count(client) -> int:
    try:
        resp = (
            client.table("ocr_staging")
            .select("id", count="exact")
            .eq("status", "pending")
            .execute()
        )
        if getattr(resp, "count", None) is not None:
            return int(resp.count)
        return len(resp.data or [])
    except Exception:
        return 0


def switch_menu_page(title: str) -> bool:
    pages = st.session_state.get("_cwm_menu_pages") or {}
    page = pages.get(title)
    if page is None:
        return False
    try:
        st.switch_page(page)
        return True
    except Exception:
        return False


def empty_cta(
    message: str,
    *,
    button_label: str | None = None,
    page_title: str | None = None,
    key: str,
) -> None:
    st.info(message)
    if button_label and page_title:
        if st.button(button_label, key=key, type="primary", use_container_width=True):
            if not switch_menu_page(page_title):
                st.caption(f"「{page_title}」메뉴로 이동해 주세요.")


def latest_price_updated_at(client) -> str | None:
    try:
        rows = (
            client.table("market_prices")
            .select("updated_at")
            .neq("ticker", "USDKRW")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            return None
        return rows[0].get("updated_at")
    except Exception:
        return None


def render_price_status_bar(client, *, any_stale: bool = False) -> None:
    """Fixed caption: last quote time + auto hint."""
    raw = latest_price_updated_at(client)
    label = "시세 없음"
    stale = True
    if raw:
        stale = is_stale(raw)
        try:
            ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            local = ts.astimezone()
            label = local.strftime("%m/%d %H:%M")
        except Exception:
            label = str(raw)[:16]
    flag = "지연" if (stale or any_stale) else "정상"
    st.markdown(
        f'<div class="np-status-bar">'
        f'<span class="np-status-dot {"stale" if flag == "지연" else "ok"}"></span>'
        f"시세 {label} · {flag} · 매시 자동 갱신"
        f'<span class="np-status-hint">({STALE_HOURS:.0f}시간 기준)</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def confirm_danger(label: str, *, key: str) -> bool:
    """Secondary confirm checkbox for destructive actions."""
    return st.checkbox(f"확인: {label}", key=key)


def section_header(title: str, subtitle: str = "") -> None:
    sub = f'<div class="np-sec-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="np-sec-head"><div class="np-sec-title">{title}</div>{sub}</div>',
        unsafe_allow_html=True,
    )
