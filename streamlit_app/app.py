"""Couples Wealth Master — Streamlit entry (auth + home)."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth import logout_and_clear, remember_login  # noqa: E402
from lib.session_persist import ensure_persistent_login  # noqa: E402
from lib.supabase_client import (  # noqa: E402
    ALLOWED_EMAILS,
    ConfigError,
    PUBLIC_APP_URL,
    SUPABASE_URL,
    get_anon_client,
    is_email_allowed,
    upsert_app_user,
)

st.set_page_config(
    page_title="Couples Wealth Master",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Mobile-friendly spacing / tap targets
st.markdown(
    """
<style>
  .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 900px; }
  div.stButton > button { width: 100%; min-height: 3rem; }
  div.stLinkButton > a { width: 100%; min-height: 3rem; display:flex; align-items:center; justify-content:center; }
  @media (max-width: 640px) {
    h1 { font-size: 1.6rem !important; }
    .block-container { padding-left: 1rem; padding-right: 1rem; }
  }
</style>
""",
    unsafe_allow_html=True,
)


def _handle_oauth_callback() -> None:
    """Capture tokens from URL hash/query after Supabase Google redirect."""
    params = st.query_params
    code = params.get("code")
    if code and not st.session_state.get("access_token"):
        try:
            client = get_anon_client()
            session = client.auth.exchange_code_for_session({"auth_code": code})
            if session and session.session:
                remember_login(
                    session.session.access_token,
                    session.session.refresh_token,
                    session.session.user,
                )
                st.query_params.clear()
                st.rerun()
        except Exception as exc:
            st.error(f"OAuth code exchange failed: {exc}")

    access = params.get("access_token")
    refresh = params.get("refresh_token")
    if access and not st.session_state.get("access_token"):
        remember_login(access, refresh, None)
        st.query_params.clear()
        st.rerun()


def _ensure_allowed_and_profile() -> bool:
    user = st.session_state.user
    if not user:
        return False
    email = (user.email or "").lower()
    if not is_email_allowed(email):
        st.error(
            f"Access denied for `{email}`. "
            "Only couple emails listed in ALLOWED_EMAILS may use this app."
        )
        if st.button("Sign out", key="denied_signout"):
            logout_and_clear()
            st.rerun()
        return False

    if not st.session_state.app_user:
        try:
            from lib.supabase_client import get_user_client

            client = get_user_client(
                st.session_state.access_token,
                st.session_state.refresh_token,
            )
            try:
                st.session_state.app_user = upsert_app_user(client, user)
            except Exception:
                from lib.supabase_client import get_service_client

                svc = get_service_client()
                st.session_state.app_user = upsert_app_user(svc, user)
        except Exception as exc:
            st.error(
                "Could not register user profile in public.users. "
                f"Ensure migrations are applied and keys are set. Details: {exc}"
            )
            return False
    return True


def login_panel() -> None:
    st.title("Couples Wealth Master")
    st.caption("부부 공동 자산 관리 — Sovereign MVP")
    st.write(
        "Google 계정으로 로그인하세요. "
        f"허용 이메일만 접근할 수 있습니다 ({len(ALLOWED_EMAILS)}명 allow-list)."
    )
    st.info("한 번 로그인하면 브라우저에 로그인 상태가 유지됩니다 (최대 60일).")

    try:
        client = get_anon_client()
    except ConfigError as exc:
        st.error(str(exc))
        st.info("`.env.example`을 `.env`로 복사한 뒤 키를 채우세요.")
        return

    redirect_to = st.text_input(
        "OAuth redirect URL",
        value=PUBLIC_APP_URL,
        help="모바일/공개 접속 시 PUBLIC_APP_URL(터널 주소)과 같아야 합니다.",
    )

    if st.button("Continue with Google", type="primary"):
        try:
            result = client.auth.sign_in_with_oauth(
                {
                    "provider": "google",
                    "options": {"redirect_to": redirect_to},
                }
            )
            url = getattr(result, "url", None) or (result.get("url") if isinstance(result, dict) else None)
            if url:
                st.link_button("Open Google OAuth", url, type="primary")
                st.markdown(f"[또는 이 링크를 탭하세요]({url})")
            else:
                st.error("Could not start OAuth — check Supabase Google provider settings.")
        except Exception as exc:
            st.error(f"OAuth start failed: {exc}")

    with st.expander("개발용: 이메일 매직 링크 / 토큰"):
        email = st.text_input("Email (must be in ALLOWED_EMAILS)")
        if st.button("Send magic link"):
            if not is_email_allowed(email):
                st.error("Email not in ALLOWED_EMAILS")
            else:
                try:
                    client.auth.sign_in_with_otp(
                        {"email": email, "options": {"email_redirect_to": redirect_to}}
                    )
                    st.success("Magic link sent (if email auth is enabled).")
                except Exception as exc:
                    st.error(f"Magic link failed: {exc}")
        access = st.text_input("access_token", type="password")
        refresh = st.text_input("refresh_token", type="password")
        if st.button("Use tokens"):
            if not access:
                st.error("access_token required")
            else:
                remember_login(access, refresh or None, None)
                st.rerun()

    st.caption(f"App URL: {PUBLIC_APP_URL} · Supabase: {SUPABASE_URL}")


def home() -> None:
    user = st.session_state.user
    app_user = st.session_state.app_user or {}
    st.title("Couples Wealth Master")
    st.success(f"Signed in as **{app_user.get('display_name', user.email)}** (`{user.email}`)")

    st.markdown(
        """
### MVP 코어 루프
1. **Upload OCR** — 잔고 스크린샷 업로드 → Gemini 파싱 → `ocr_staging` (pending)
2. **Review Staging** — 검토/수정 후 승인 → 트리거가 `trades` / `holdings`에 커밋
3. **Dashboard** — 시세 새로고침 · 순자산/수익률
4. **Tax Report** — 해외주식 양도세 추정 (250만원 공제 · 22%)
5. **Notifications** — Web Push 구독 · 브리핑/백업 수동 실행
6. **Wealth Chat** — 내 자산 데이터만 근거로 Gemini와 자유 대화
7. **Asset Flows** — 매매·배당·현금·부채·손익 전 흐름 기록

사이드바에서 페이지를 선택하세요.
"""
    )

    if st.button("Sign out"):
        logout_and_clear()
        st.rerun()


def main() -> None:
    ensure_persistent_login()
    _handle_oauth_callback()

    if not st.session_state.get("access_token") or not st.session_state.get("user"):
        login_panel()
        return

    if not _ensure_allowed_and_profile():
        return

    home()


if __name__ == "__main__":
    main()
else:
    main()
