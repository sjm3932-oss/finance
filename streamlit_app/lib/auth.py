"""Shared Streamlit auth helpers."""

from __future__ import annotations

import streamlit as st

from lib.supabase_client import (
    ConfigError,
    get_user_client,
    is_email_allowed,
    upsert_app_user,
)


def require_auth():
    access = st.session_state.get("access_token")
    user = st.session_state.get("user")
    if not access or not user:
        st.warning("홈에서 먼저 로그인하세요.")
        st.stop()
    if not is_email_allowed(getattr(user, "email", None)):
        st.error("Access denied")
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
        st.error(f"Could not register user profile: {exc}")
        st.stop()
    return st.session_state.app_user
