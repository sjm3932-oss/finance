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
    ConfigError,
    PUBLIC_APP_URL,
    get_anon_client,
    is_email_allowed,
    upsert_app_user,
)
from lib.theme import apply_theme, page_hero, user_chip  # noqa: E402

st.set_page_config(
    page_title="부부 자산 마스터",
    page_icon="💚",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme(max_width=920)


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
                st.session_state._cwm_await_cookie = True
                st.session_state._cwm_cookie_tries = 0
                st.query_params.clear()
                st.rerun()
        except Exception as exc:
            st.error(f"로그인 코드 교환 실패: {exc}")

    access = params.get("access_token")
    refresh = params.get("refresh_token")
    if access and not st.session_state.get("access_token"):
        remember_login(access, refresh, None)
        st.session_state._cwm_await_cookie = True
        st.session_state._cwm_cookie_tries = 0
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
    page_hero(
        "부부 자산 마스터",
        "Google로 로그인하세요.",
    )

    try:
        client = get_anon_client()
    except ConfigError as exc:
        st.error(str(exc))
        return

    redirect_to = PUBLIC_APP_URL
    try:
        result = client.auth.sign_in_with_oauth(
            {
                "provider": "google",
                "options": {"redirect_to": redirect_to},
            }
        )
        url = getattr(result, "url", None) or (result.get("url") if isinstance(result, dict) else None)
        if url:
            st.link_button("Google로 로그인", url, type="primary")
        else:
            st.error("로그인을 시작할 수 없습니다. 잠시 후 다시 시도해 주세요.")
    except Exception as exc:
        st.error(f"로그인 준비 실패: {exc}")


def home() -> None:
    user = st.session_state.user
    app_user = st.session_state.app_user or {}
    name = app_user.get("display_name") or (user.email or "회원")

    page_hero(
        "오늘의 자산 한눈에",
        "왼쪽 메뉴에서 업로드·대시보드·챗을 바로 시작하세요.",
    )
    user_chip(str(name), user.email or "")

    st.markdown(
        """
<div class="np-section">
  <h3>바로가기</h3>
  <div class="np-menu-grid">
    <div class="np-menu-item"><div class="np-menu-num">1</div><div class="np-menu-body"><strong>OCR 업로드</strong><span>잔고 스크린샷 → AI 파싱 → 스테이징</span></div></div>
    <div class="np-menu-item"><div class="np-menu-num">2</div><div class="np-menu-body"><strong>스테이징 검토</strong><span>검토·수정 후 승인하면 보유·매매 반영</span></div></div>
    <div class="np-menu-item"><div class="np-menu-num">3</div><div class="np-menu-body"><strong>대시보드</strong><span>한눈에 · 종목 · 자산 흐름 · 기록하기</span></div></div>
    <div class="np-menu-item"><div class="np-menu-num">4</div><div class="np-menu-body"><strong>세금 리포트</strong><span>해외주식 양도세 추정 (기본공제 250만원)</span></div></div>
    <div class="np-menu-item"><div class="np-menu-num">5</div><div class="np-menu-body"><strong>알림·작업</strong><span>푸시 구독 · 브리핑/백업 수동 실행</span></div></div>
    <div class="np-menu-item"><div class="np-menu-num">6</div><div class="np-menu-body"><strong>자산 챗</strong><span>내 자산 데이터 기준 AI 대화</span></div></div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    if st.button("로그아웃", type="secondary"):
        logout_and_clear()
        st.rerun()


def _await_sid_cookie_if_needed() -> None:
    """After login, keep rewriting the short sid cookie until the browser has it."""
    if not st.session_state.get("_cwm_await_cookie"):
        return
    sid = st.session_state.get("cwm_sid")
    if not sid or not st.session_state.get("access_token"):
        st.session_state._cwm_await_cookie = False
        return

    from lib.session_persist import read_sid_cookie, write_sid_cookie

    if read_sid_cookie() == sid:
        st.session_state._cwm_await_cookie = False
        st.session_state._cwm_cookie_tries = 0
        return

    st.session_state._cwm_force_cookie_write = True
    write_sid_cookie(sid)
    tries = int(st.session_state.get("_cwm_cookie_tries") or 0) + 1
    st.session_state._cwm_cookie_tries = tries
    st.info("로그인 상태 저장 중… 잠시만 기다려 주세요.")
    if tries < 10:
        st.rerun()
    st.session_state._cwm_await_cookie = False
    st.warning(
        "브라우저 쿠키 저장이 지연되고 있습니다. "
        "이 탭에서는 유지되지만, 새로고침 후에도 유지되지 않으면 "
        "브라우저 쿠키를 허용한 뒤 다시 로그인해 주세요."
    )


def main() -> None:
    ensure_persistent_login()
    _handle_oauth_callback()
    _await_sid_cookie_if_needed()

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
