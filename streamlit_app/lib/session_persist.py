"""Persist Supabase auth tokens across Streamlit browser sessions via cookies."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import streamlit as st

COOKIE_ACCESS = "cwm_access_token"
COOKIE_REFRESH = "cwm_refresh_token"
COOKIE_DAYS = 60


def _is_first_call_this_run(flag_key: str) -> bool:
    """Return True only for the first call in the current script run.

    Uses ScriptRunContext.fragment_ids_this_run identity as a cheap run marker:
    a new ctx cursors/shared object appears across runs; we store marker id.
    """
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        ctx = get_script_run_ctx()
        marker = id(ctx.shared) if ctx is not None else None
    except Exception:
        marker = None

    meta_key = f"{flag_key}__marker"
    if st.session_state.get(meta_key) != marker:
        st.session_state[meta_key] = marker
        st.session_state[flag_key] = False

    if st.session_state.get(flag_key):
        return False
    st.session_state[flag_key] = True
    return True


def get_cookie_manager():
    """Mount CookieManager once per script run (never twice)."""
    import extra_streamlit_components as stx

    if _is_first_call_this_run("_cwm_cm_mounted"):
        st.session_state._cwm_cm = stx.CookieManager(key="cwm_cm_init")
    return st.session_state._cwm_cm


def _cookie_options():
    from lib.supabase_client import PUBLIC_APP_URL

    secure = PUBLIC_APP_URL.startswith("https://")
    return {
        "expires_at": datetime.now(timezone.utc) + timedelta(days=COOKIE_DAYS),
        "max_age": float(COOKIE_DAYS * 24 * 3600),
        "path": "/",
        "secure": secure,
        "same_site": "lax",
    }


def read_auth_cookies() -> tuple[str | None, str | None]:
    cm = get_cookie_manager()
    # Prefer values already loaded by CookieManager.__init__ getAll.
    # Optionally refresh once per run if still empty (hydration).
    access = cm.get(COOKIE_ACCESS)
    refresh = cm.get(COOKIE_REFRESH)
    if not access and not refresh and _is_first_call_this_run("_cwm_cm_get_all"):
        data = cm.get_all(key="cwm_cm_get_all") or {}
        if isinstance(data, dict):
            cm.cookies = data
            access = data.get(COOKIE_ACCESS)
            refresh = data.get(COOKIE_REFRESH)
    return access or None, refresh or None


def save_auth_cookies(access_token: str, refresh_token: str | None) -> None:
    if not _is_first_call_this_run("_cwm_cm_write"):
        return

    cm = get_cookie_manager()
    opts = _cookie_options()
    if access_token and cm.get(COOKIE_ACCESS) != access_token:
        cm.set(COOKIE_ACCESS, access_token, key="cwm_cm_set_access", **opts)
    if refresh_token and cm.get(COOKIE_REFRESH) != refresh_token:
        cm.set(COOKIE_REFRESH, refresh_token, key="cwm_cm_set_refresh", **opts)


def clear_auth_cookies() -> None:
    if not _is_first_call_this_run("_cwm_cm_clear"):
        return
    cm = get_cookie_manager()
    try:
        cm.delete(COOKIE_ACCESS, key="cwm_cm_del_access")
    except Exception:
        pass
    try:
        cm.delete(COOKIE_REFRESH, key="cwm_cm_del_refresh")
    except Exception:
        pass


def persist_session_tokens() -> None:
    access = st.session_state.get("access_token")
    refresh = st.session_state.get("refresh_token")
    if access:
        save_auth_cookies(access, refresh)


def refresh_supabase_session() -> bool:
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
    if not _is_first_call_this_run("_cwm_ensure"):
        return

    st.session_state.setdefault("access_token", None)
    st.session_state.setdefault("refresh_token", None)
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("app_user", None)

    # Mount manager once
    get_cookie_manager()
    access_c, refresh_c = read_auth_cookies()

    if not st.session_state.get("access_token") and (access_c or refresh_c):
        st.session_state.access_token = access_c
        st.session_state.refresh_token = refresh_c

    if st.session_state.get("user"):
        return

    if st.session_state.get("refresh_token") or st.session_state.get("access_token"):
        ok = refresh_supabase_session()
        if ok:
            if not st.session_state.get("_cwm_restored_once"):
                st.session_state._cwm_restored_once = True
                st.rerun()
            return
        st.session_state.access_token = None
        st.session_state.refresh_token = None
        st.session_state.user = None
        st.session_state.app_user = None
        clear_auth_cookies()
