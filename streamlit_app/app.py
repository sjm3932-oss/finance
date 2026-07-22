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
    page_title="부부 자산 마스터",
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
            st.error(f"로그인 코드 교환 실패: {exc}")

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
            f"`{email}` 은(는) 접근할 수 없습니다. "
            "허용 이메일에 등록된 부부 계정만 사용할 수 있습니다."
        )
        if st.button("로그아웃", key="denied_signout"):
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
                "사용자 프로필 등록에 실패했습니다. "
                f"마이그레이션과 키 설정을 확인하세요. 상세: {exc}"
            )
            return False
    return True


def login_panel() -> None:
    st.title("부부 자산 마스터")
    st.caption("부부 공동 자산 관리")
    st.write(
        "Google 계정으로 로그인하세요. "
        f"허용된 이메일만 접근할 수 있습니다 (허용 {len(ALLOWED_EMAILS)}명)."
    )
    st.info("한 번 로그인하면 브라우저에 로그인 상태가 유지됩니다 (최대 60일).")

    try:
        client = get_anon_client()
    except ConfigError as exc:
        st.error(str(exc))
        st.info("`.env.example`을 `.env`로 복사한 뒤 키를 채우세요.")
        return

    redirect_to = st.text_input(
        "로그인 후 돌아갈 주소",
        value=PUBLIC_APP_URL,
        help="모바일/공개 접속 시 PUBLIC_APP_URL(터널 주소)과 같아야 합니다.",
    )

    if st.button("Google로 계속", type="primary"):
        try:
            result = client.auth.sign_in_with_oauth(
                {
                    "provider": "google",
                    "options": {"redirect_to": redirect_to},
                }
            )
            url = getattr(result, "url", None) or (result.get("url") if isinstance(result, dict) else None)
            if url:
                st.link_button("Google 로그인 열기", url, type="primary")
                st.markdown(f"[또는 이 링크를 탭하세요]({url})")
            else:
                st.error("로그인을 시작할 수 없습니다. Supabase Google 설정을 확인하세요.")
        except Exception as exc:
            st.error(f"로그인 시작 실패: {exc}")

    with st.expander("개발용: 이메일 매직 링크 / 토큰"):
        email = st.text_input("이메일 (허용 목록에 있어야 함)")
        if st.button("매직 링크 보내기"):
            if not is_email_allowed(email):
                st.error("허용되지 않은 이메일입니다")
            else:
                try:
                    client.auth.sign_in_with_otp(
                        {"email": email, "options": {"email_redirect_to": redirect_to}}
                    )
                    st.success("매직 링크를 보냈습니다 (이메일 로그인이 켜져 있는 경우).")
                except Exception as exc:
                    st.error(f"매직 링크 실패: {exc}")
        access = st.text_input("액세스 토큰", type="password")
        refresh = st.text_input("리프레시 토큰", type="password")
        if st.button("토큰으로 로그인"):
            if not access:
                st.error("액세스 토큰이 필요합니다")
            else:
                remember_login(access, refresh or None, None)
                st.rerun()

    st.caption(f"앱 주소: {PUBLIC_APP_URL}")


def home() -> None:
    user = st.session_state.user
    app_user = st.session_state.app_user or {}
    st.title("부부 자산 마스터")
    st.success(f"**{app_user.get('display_name', user.email)}** 님으로 로그인됨 (`{user.email}`)")

    st.markdown(
        """
### 메뉴 안내
1. **OCR 업로드** — 잔고 스크린샷 → AI 파싱 → 스테이징(대기)
2. **스테이징 검토** — 검토/수정 후 승인 → 보유·매매 반영
3. **대시보드** — 시세·순자산·종목별 추이
4. **세금 리포트** — 해외주식 양도세 추정 (기본공제 250만원 · 22%)
5. **알림·작업** — 푸시 구독 · 브리핑/백업 수동 실행
6. **자산 챗** — 내 자산 데이터 기준 AI 대화
7. **자산 흐름** — 매매·배당·현금·부채·손익 기록

왼쪽 사이드바에서 페이지를 선택하세요.
"""
    )

    if st.button("로그아웃"):
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
