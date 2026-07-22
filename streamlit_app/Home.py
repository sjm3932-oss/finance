"""Couples Wealth Master — Home (auth + menu index)."""

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
    page_title="홈 · 부부 자산 마스터",
    page_icon="💚",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme(max_width=920)

# Sidebar / home menu registry (path relative to streamlit_app/)
MENU_ITEMS = [
    {
        "title": "OCR 업로드",
        "path": "pages/1_OCR_업로드.py",
        "desc": "잔고·매매·배당 스크린샷 → AI 파싱 → 스테이징",
    },
    {
        "title": "스테이징 검토",
        "path": "pages/2_스테이징_검토.py",
        "desc": "검토·수정 후 승인하면 매매·배당·보유 반영",
    },
    {
        "title": "대시보드",
        "path": "pages/3_대시보드.py",
        "desc": "한눈에 · 종목 · 실현손익 · 자산 흐름 · 기록하기",
    },
    {
        "title": "세금 리포트",
        "path": "pages/4_세금_리포트.py",
        "desc": "해외주식 양도세 추정 (기본공제 250만원 · 22%)",
    },
    {
        "title": "알림·작업",
        "path": "pages/5_알림_작업.py",
        "desc": "푸시 구독 · 브리핑/백업 수동 실행",
    },
    {
        "title": "자산 챗",
        "path": "pages/6_자산_챗.py",
        "desc": "내 자산 데이터 기준 AI 대화",
    },
]


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


def _oauth_login_url() -> str | None:
    try:
        client = get_anon_client()
        result = client.auth.sign_in_with_oauth(
            {
                "provider": "google",
                "options": {"redirect_to": PUBLIC_APP_URL},
            }
        )
        return getattr(result, "url", None) or (
            result.get("url") if isinstance(result, dict) else None
        )
    except ConfigError as exc:
        st.session_state["_cwm_login_cfg_error"] = str(exc)
        return None
    except Exception as exc:
        st.session_state["_cwm_login_cfg_error"] = str(exc)
        return None


def render_top_right_auth(*, logged_in: bool) -> None:
    """Fixed top-right login / logout control."""
    if logged_in:
        st.markdown('<div class="np-top-auth-slot">', unsafe_allow_html=True)
        if st.button("로그아웃", key="top_logout", type="secondary"):
            logout_and_clear()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    url = _oauth_login_url()
    err = st.session_state.pop("_cwm_login_cfg_error", None)
    if err:
        st.error(err)
        return
    if not url:
        st.error("로그인을 준비할 수 없습니다.")
        return

    st.markdown(
        f'<a class="np-top-auth-btn" href="{url}" target="_self" rel="noopener">Google로 로그인</a>',
        unsafe_allow_html=True,
    )


def render_menu_index(*, can_navigate: bool) -> None:
    """Clickable menu index — each row navigates on press."""
    st.markdown('<div class="np-section np-home-menu">', unsafe_allow_html=True)
    st.markdown("### 메뉴")
    if can_navigate:
        st.caption("항목을 누르면 해당 화면으로 이동합니다.")
    else:
        st.caption("오른쪽 위 **Google로 로그인** 후 메뉴를 눌러 이동하세요.")

    for i, item in enumerate(MENU_ITEMS, start=1):
        label = f"{i}. {item['title']}  —  {item['desc']}"
        clicked = st.button(
            label,
            key=f"home_go_{i}",
            type="primary" if can_navigate else "secondary",
            use_container_width=True,
            disabled=not can_navigate,
        )
        if clicked and can_navigate:
            try:
                st.switch_page(item["path"])
            except Exception as exc:
                st.error(f"이동 실패: {exc}")

    st.markdown("</div>", unsafe_allow_html=True)


def home_logged_out() -> None:
    render_top_right_auth(logged_in=False)
    page_hero("홈", "부부 공동 자산 관리 — 메뉴를 선택해 시작하세요.")
    render_menu_index(can_navigate=False)


def home_logged_in() -> None:
    user = st.session_state.user
    app_user = st.session_state.app_user or {}
    name = app_user.get("display_name") or (user.email or "회원")

    render_top_right_auth(logged_in=True)
    page_hero("홈", "메뉴를 눌러 원하는 화면으로 이동하세요.")
    user_chip(str(name), user.email or "")
    render_menu_index(can_navigate=True)


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

    logged_in = bool(
        st.session_state.get("access_token") and st.session_state.get("user")
    )
    if not logged_in:
        home_logged_out()
        return

    if not _ensure_allowed_and_profile():
        return

    home_logged_in()


if __name__ == "__main__":
    main()
else:
    main()
