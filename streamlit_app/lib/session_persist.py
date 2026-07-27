"""Persist Supabase auth across Streamlit reruns / page changes / reloads.

Strategy:
- Browser cookie holds only a short session id (`cwm_sid`)
- Access/refresh JWTs live in a local server-side store keyed by that id
- CookieManager keeps rewriting the sid until it appears in st.context.cookies
- Transient refresh failures do NOT wipe the session
"""

from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timedelta, timezone

import streamlit as st

from lib import session_store

COOKIE_SID = "cwm_sid"
# Legacy cookies (migrated away — deleted when seen)
COOKIE_ACCESS = "cwm_access_token"
COOKIE_REFRESH = "cwm_refresh_token"
COOKIE_DAYS = 60


def _is_first_call_this_run(flag_key: str) -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        ctx = get_script_run_ctx()
        marker = id(ctx) if ctx is not None else None
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


def _cookie_options() -> dict:
    from lib.supabase_client import PUBLIC_APP_URL

    secure = str(PUBLIC_APP_URL).startswith("https://")
    return {
        "expires_at": datetime.now(timezone.utc) + timedelta(days=COOKIE_DAYS),
        "max_age": float(COOKIE_DAYS * 24 * 3600),
        "path": "/",
        "secure": secure,
        "same_site": "lax",
    }


def _get_cookie_manager():
    """Mount CookieManager at most once per script run."""
    import extra_streamlit_components as stx

    if _is_first_call_this_run("_cwm_cm_mounted"):
        st.session_state._cwm_cm = stx.CookieManager(key="cwm_cm_sid")
    return st.session_state._cwm_cm


def _request_cookies():
    try:
        return st.context.cookies
    except Exception:
        return None


def read_sid_cookie() -> str | None:
    cookies = _request_cookies()
    if not cookies:
        return None
    sid = cookies.get(COOKIE_SID)
    return sid or None


def read_legacy_token_cookies() -> tuple[str | None, str | None]:
    cookies = _request_cookies()
    if not cookies:
        return None, None
    return cookies.get(COOKIE_ACCESS) or None, cookies.get(COOKIE_REFRESH) or None


def write_sid_cookie(sid: str) -> None:
    """Queue a CookieManager write for the short session id (idempotent per run)."""
    if not sid:
        return
    current = read_sid_cookie()
    if current == sid and not st.session_state.get("_cwm_force_cookie_write"):
        return
    if not _is_first_call_this_run("_cwm_cm_write"):
        return
    cm = _get_cookie_manager()
    opts = _cookie_options()
    cm.set(COOKIE_SID, sid, key="cwm_set_sid", **opts)
    # Drop legacy oversized JWT cookies if still present
    try:
        la, lr = read_legacy_token_cookies()
        if la or lr:
            cm.delete(COOKIE_ACCESS, key="cwm_del_access_legacy")
            cm.delete(COOKIE_REFRESH, key="cwm_del_refresh_legacy")
    except Exception:
        pass
    st.session_state._cwm_force_cookie_write = False


def clear_auth_cookies() -> None:
    if not _is_first_call_this_run("_cwm_cm_clear"):
        return
    cm = _get_cookie_manager()
    for name, key in (
        (COOKIE_SID, "cwm_del_sid"),
        (COOKIE_ACCESS, "cwm_del_access"),
        (COOKIE_REFRESH, "cwm_del_refresh"),
    ):
        try:
            cm.delete(name, key=key)
        except Exception:
            pass


def _jwt_exp(token: str | None) -> int | None:
    if not token or token.count(".") < 2:
        return None
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")))
        exp = payload.get("exp")
        return int(exp) if exp is not None else None
    except Exception:
        return None


def _access_needs_refresh(access: str | None, skew_sec: int = 120) -> bool:
    exp = _jwt_exp(access)
    if exp is None:
        return True
    return exp <= int(time.time()) + skew_sec


def _is_fatal_auth_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    needles = (
        "invalid refresh token",
        "refresh token not found",
        "invalid jwt",
        "session not found",
        "user not found",
        "token is expired",
        "invalid claim",
        "401",
        "403",
    )
    return any(n in msg for n in needles)


def _bind_sid_and_store(access: str, refresh: str | None) -> str:
    sid = st.session_state.get("cwm_sid") or read_sid_cookie() or session_store.new_sid()
    st.session_state.cwm_sid = sid
    session_store.save_tokens(sid, access, refresh)
    write_sid_cookie(sid)
    return sid


def persist_session_tokens() -> None:
    access = st.session_state.get("access_token")
    refresh = st.session_state.get("refresh_token")
    if not access:
        return
    _bind_sid_and_store(access, refresh)


def refresh_supabase_session(*, force: bool = False) -> bool:
    """Hydrate/refresh Supabase user into session_state. Returns True on success."""
    from lib.supabase_client import get_anon_client

    refresh = st.session_state.get("refresh_token")
    access = st.session_state.get("access_token")
    if not refresh and not access:
        return False

    try:
        client = get_anon_client()

        # Prefer set_session: refreshes only when access JWT is expired.
        if access and refresh and (force or _access_needs_refresh(access)):
            try:
                result = client.auth.set_session(access, refresh)
                session = getattr(result, "session", None)
                if session is None and isinstance(result, dict):
                    session = result.get("session")
                if session:
                    st.session_state.access_token = session.access_token
                    st.session_state.refresh_token = session.refresh_token or refresh
                    st.session_state.user = session.user
                    persist_session_tokens()
                    return True
            except Exception as exc:
                if _is_fatal_auth_error(exc):
                    st.session_state["_cwm_auth_fatal"] = str(exc)
                    return False
                # Transient — fall through to get_user with current access

        if access and not _access_needs_refresh(access, skew_sec=0):
            user_resp = client.auth.get_user(access)
            if user_resp and user_resp.user:
                st.session_state.user = user_resp.user
                persist_session_tokens()
                return True

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
            except Exception as exc:
                if _is_fatal_auth_error(exc):
                    st.session_state["_cwm_auth_fatal"] = str(exc)
                    return False
                return False

        if access:
            user_resp = client.auth.get_user(access)
            if user_resp and user_resp.user:
                st.session_state.user = user_resp.user
                persist_session_tokens()
                return True
    except Exception as exc:
        if _is_fatal_auth_error(exc):
            st.session_state["_cwm_auth_fatal"] = str(exc)
            return False
        return False
    return False


def _wipe_local_auth(*, clear_cookie: bool = False) -> None:
    sid = st.session_state.get("cwm_sid") or read_sid_cookie()
    if sid:
        session_store.delete_tokens(sid)
    for key in ("access_token", "refresh_token", "user", "app_user", "cwm_sid"):
        st.session_state[key] = None
    if clear_cookie:
        clear_auth_cookies()


def ensure_persistent_login() -> None:
    """Hydrate session from sid cookie + server store; refresh when needed."""
    if not _is_first_call_this_run("_cwm_ensure"):
        # Still keep trying to plant the sid cookie every run until visible
        sid = st.session_state.get("cwm_sid")
        if sid and st.session_state.get("access_token"):
            write_sid_cookie(sid)
        return

    st.session_state.setdefault("access_token", None)
    st.session_state.setdefault("refresh_token", None)
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("app_user", None)
    st.session_state.setdefault("cwm_sid", None)

    sid_c = read_sid_cookie()
    legacy_a, legacy_r = read_legacy_token_cookies()

    # Restore tokens from server store via cookie sid
    if not st.session_state.get("access_token"):
        sid = st.session_state.get("cwm_sid") or sid_c
        if sid:
            stored = session_store.load_tokens(sid)
            if stored:
                st.session_state.cwm_sid = sid
                st.session_state.access_token = stored.get("access_token")
                st.session_state.refresh_token = stored.get("refresh_token")
        # One-time migration from legacy JWT cookies
        if not st.session_state.get("access_token") and (legacy_a or legacy_r):
            st.session_state.access_token = legacy_a
            st.session_state.refresh_token = legacy_r

    # Already have a user object this Streamlit session — keep cookie planted
    if st.session_state.get("user") and st.session_state.get("access_token"):
        persist_session_tokens()
        # Soft refresh near expiry
        if _access_needs_refresh(st.session_state.get("access_token")):
            ok = refresh_supabase_session()
            if not ok and st.session_state.get("_cwm_auth_fatal"):
                _wipe_local_auth(clear_cookie=True)
        return

    if st.session_state.get("refresh_token") or st.session_state.get("access_token"):
        ok = refresh_supabase_session()
        if ok:
            persist_session_tokens()
            if not st.session_state.get("_cwm_restored_once"):
                st.session_state._cwm_restored_once = True
                st.rerun()
            return
        # Only wipe on definitive auth failure — keep tokens on network blips
        if st.session_state.get("_cwm_auth_fatal"):
            _wipe_local_auth(clear_cookie=True)
        return
