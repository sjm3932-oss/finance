"""Shared Streamlit auth helpers with cookie-backed persistence."""

from __future__ import annotations

import streamlit as st

from lib.session_persist import (
    clear_auth_cookies,
    ensure_persistent_login,
    persist_session_tokens,
)
from lib.supabase_client import (
    ConfigError,
    get_user_client,
    is_email_allowed,
    upsert_app_user,
)


def require_auth():
    ensure_persistent_login()
    access = st.session_state.get("access_token")
    user = st.session_state.get("user")
    if not access or not user:
        st.warning("홈에서 먼저 로그인하세요. (한 번 로그인하면 다음부터 유지됩니다)")
        st.stop()
    if not is_email_allowed(getattr(user, "email", None)):
        st.error("접근이 거부되었습니다")
        st.stop()
    refresh = st.session_state.get("refresh_token")
    try:
        client = get_user_client(access, refresh)
    except ConfigError as exc:
        st.error(str(exc))
        st.stop()
    return user, client


def ensure_profile(user, client):
    if st.session_state.get("app_user"):
        return st.session_state.app_user
    try:
        st.session_state.app_user = upsert_app_user(client, user)
    except Exception as exc:
        st.error(f"사용자 프로필을 등록할 수 없습니다: {exc}")
        st.stop()
    return st.session_state.app_user


def logout_and_clear() -> None:
    try:
        from lib.supabase_client import get_anon_client

        get_anon_client().auth.sign_out()
    except Exception:
        pass
    try:
        from lib import session_store
        from lib.session_persist import read_sid_cookie

        sid = st.session_state.get("cwm_sid") or read_sid_cookie()
        if sid:
            session_store.delete_tokens(sid)
    except Exception:
        pass
    for key in ("access_token", "refresh_token", "user", "app_user", "cwm_sid", "_cwm_auth_fatal"):
        st.session_state[key] = None
    try:
        clear_auth_cookies()
    except Exception:
        pass


def remember_login(access_token: str, refresh_token: str | None, user=None) -> None:
    st.session_state.access_token = access_token
    st.session_state.refresh_token = refresh_token
    st.session_state._cwm_auth_fatal = None
    st.session_state._cwm_force_cookie_write = True
    if user is not None:
        st.session_state.user = user
    persist_session_tokens()
