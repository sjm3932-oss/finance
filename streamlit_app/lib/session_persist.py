"""Persist Supabase auth tokens across Streamlit browser sessions via cookies."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import streamlit as st

COOKIE_ACCESS = "cwm_access_token"
COOKIE_REFRESH = "cwm_refresh_token"
COOKIE_DAYS = 60


def get_cookie_manager():
    """Instantiate every run (component key keeps identity stable)."""
    import extra_streamlit_components as stx

    from lib.supabase_client import PUBLIC_APP_URL

    # Ensure manager is created early so cookies hydrate this run
    return stx.CookieManager(key="cwm_cookie_manager")


def _cookie_options():
    from lib.supabase_client import PUBLIC_APP_URL

    secure = PUBLIC_APP_URL.startswith("https://")
    return {
        "expires_at": datetime.now(timezone.utc) + timedelta(days=COOKIE_DAYS),
        "max_age": float(COOKIE_DAYS * 24 * 3600),
        "path": "/",
        "secure": secure,
        "same_site": "lax",  # required so OAuth redirect can keep cookies
    }


def save_auth_cookies(access_token: str, refresh_token: str | None) -> None:
    cm = get_cookie_manager()
    opts = _cookie_options()
    if access_token:
        cm.set(COOKIE_ACCESS, access_token, key="cwm_set_access", **opts)
    if refresh_token:
        cm.set(COOKIE_REFRESH, refresh_token, key="cwm_set_refresh", **opts)


def clear_auth_cookies() -> None:
    cm = get_cookie_manager()
    try:
        cm.delete(COOKIE_ACCESS, key="cwm_del_access")
    except Exception:
        pass
    try:
        cm.delete(COOKIE_REFRESH, key="cwm_del_refresh")
    except Exception:
        pass


def read_auth_cookies() -> tuple[str | None, str | None]:
    cm = get_cookie_manager()
    # Refresh cookie map from browser
    cm.get_all(key="cwm_get_all")
    access = cm.get(COOKIE_ACCESS) or None
    refresh = cm.get(COOKIE_REFRESH) or None
    return access, refresh


def persist_session_tokens() -> None:
    access = st.session_state.get("access_token")
    refresh = st.session_state.get("refresh_token")
    if access:
        save_auth_cookies(access, refresh)


def refresh_supabase_session() -> bool:
    """Refresh access token using refresh_token; update session + cookies."""
    from lib.supabase_client import get_anon_client

    refresh = st.session_state.get("refresh_token")
    access = st.session_state.get("access_token")
    if not refresh and not access:
        return False
    try:
        client = get_anon_client()
        if refresh:
            try:
                result = client.auth.refresh_session(refresh)
                session = getattr(result, "session", None)
                if session is None and isinstance(result, dict):
                    session = result.get("session")
                if session:
                    st.session_state.access_token = session.access_token
                    st.session_state.refresh_token = session.refresh_token or refresh
                    st.session_state.user = session.user
                    persist_session_tokens()
                    return True
            except Exception:
                pass
        if access and refresh:
            client.auth.set_session(access, refresh)
            user_resp = client.auth.get_user(access)
            if user_resp and user_resp.user:
                st.session_state.user = user_resp.user
                return True
        if access:
            user_resp = client.auth.get_user(access)
            if user_resp and user_resp.user:
                st.session_state.user = user_resp.user
                return True
    except Exception:
        return False
    return False


def ensure_persistent_login() -> None:
    """Hydrate session from cookies and refresh tokens when needed."""
    st.session_state.setdefault("access_token", None)
    st.session_state.setdefault("refresh_token", None)
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("app_user", None)

    # Always mount cookie manager so browser cookies sync
    access_c, refresh_c = read_auth_cookies()

    if not st.session_state.get("access_token") and (access_c or refresh_c):
        st.session_state.access_token = access_c
        st.session_state.refresh_token = refresh_c

    if st.session_state.get("user"):
        return

    if st.session_state.get("refresh_token") or st.session_state.get("access_token"):
        ok = refresh_supabase_session()
        if ok:
            # Avoid remount loops: only rerun once after cookie restore
            if not st.session_state.get("_cwm_restored_once"):
                st.session_state._cwm_restored_once = True
                st.rerun()
            return
        # Invalid tokens
        st.session_state.access_token = None
        st.session_state.refresh_token = None
        st.session_state.user = None
        st.session_state.app_user = None
        clear_auth_cookies()
