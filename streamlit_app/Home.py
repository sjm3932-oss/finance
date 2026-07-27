"""부자뚱 — Home (auth + menu) and sidebar navigation."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth import logout_and_clear, remember_login  # noqa: E402
from lib.env_boot import app_base_url, hydrate_env, is_ephemeral_app_url  # noqa: E402
from lib.session_persist import ensure_persistent_login  # noqa: E402
from lib.supabase_client import (  # noqa: E402
    ConfigError,
    get_anon_client,
    get_stable_app_url,
    is_email_allowed,
    upsert_app_user,
)

hydrate_env()
from lib.theme import apply_theme, page_hero, user_chip  # noqa: E402

st.set_page_config(
    page_title="부자뚱",
    page_icon="💚",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme(max_width=920)

MENU_TITLES = ("내 자산", "자산 챗", "기록하기", "승인하기")


def _handle_oauth_callback() -> None:
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


def _await_sid_cookie_if_needed() -> None:
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
    st.info("로그인 상태 저장 중…")
    if tries < 10:
        st.rerun()
    st.session_state._cwm_await_cookie = False


def _oauth_login_url() -> str | None:
    try:
        client = get_anon_client()
        redirect_to = get_stable_app_url()
        if is_ephemeral_app_url(redirect_to):
            st.session_state["_cwm_login_cfg_error"] = (
                "PUBLIC_APP_URL이 임시 터널입니다. "
                "Secrets에 https://richddoong.streamlit.app 을 넣으세요."
            )
            return None
        result = client.auth.sign_in_with_oauth(
            {
                "provider": "google",
                "options": {"redirect_to": redirect_to},
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


def _ensure_allowed_and_profile() -> bool:
    user = st.session_state.user
    if not user:
        return False
    email = (user.email or "").lower()
    if not is_email_allowed(email):
        st.error(f"`{email}` 은(는) 접근할 수 없습니다.")
        if st.button("로그아웃", key="denied_signout"):
            logout_and_clear()
            st.rerun()
        return False

    if not st.session_state.app_user:
        try:
            from lib.supabase_client import get_service_client, get_user_client

            client = get_user_client(
                st.session_state.access_token,
                st.session_state.refresh_token,
            )
            try:
                st.session_state.app_user = upsert_app_user(client, user)
            except Exception:
                st.session_state.app_user = upsert_app_user(get_service_client(), user)
        except Exception as exc:
            st.error(f"프로필 등록 실패: {exc}")
            return False
    return True


def _render_auth(*, logged_in: bool) -> None:
    if logged_in:
        if st.button("로그아웃", key="home_logout", type="secondary", use_container_width=True):
            logout_and_clear()
            st.rerun()
        return

    err = st.session_state.pop("_cwm_login_cfg_error", None)
    if err:
        st.error(err)
        return
    url = _oauth_login_url()
    if not url:
        st.error("로그인을 준비할 수 없습니다.")
        return
    st.link_button("Google로 로그인", url, type="primary", use_container_width=True)


def _render_menu_buttons(*, pages: dict | None, can_navigate: bool, pending_approve: int = 0) -> None:
    """Login 아래 메인 메뉴 버튼 (예전 Home TOC)."""
    st.markdown('<div class="np-section np-home-menu">', unsafe_allow_html=True)
    st.markdown("### 메뉴")
    for title in MENU_TITLES:
        label = title
        if title == "승인하기" and pending_approve > 0:
            label = f"승인하기 ({pending_approve})"
        clicked = st.button(
            label,
            key=f"home_go_{title}",
            type="primary" if can_navigate else "secondary",
            use_container_width=True,
            disabled=not can_navigate,
        )
        if clicked and can_navigate and pages and title in pages:
            try:
                st.switch_page(pages[title])
            except Exception as exc:
                st.error(f"이동 실패: {exc}")
    st.markdown("</div>", unsafe_allow_html=True)


def _show_logged_out_home() -> None:
    page_hero("홈", "부부 공동 자산 관리 — 로그인 후 이용하세요.")
    base = app_base_url()
    if is_ephemeral_app_url(base):
        st.warning("PUBLIC_APP_URL을 Streamlit Cloud 주소로 설정하세요.")
    else:
        st.caption(f"접속 주소: {base}")
    _render_auth(logged_in=False)
    _render_menu_buttons(pages=None, can_navigate=False)


def _make_pages() -> tuple:
    views = ROOT / "views"
    home = st.Page(_render_logged_in_home, title="홈", default=True)
    dash = st.Page(str(views / "dashboard.py"), title="내 자산")
    chat = st.Page(str(views / "wealth_chat.py"), title="자산 챗")
    record = st.Page(str(views / "record.py"), title="기록하기")
    approve = st.Page(str(views / "approve.py"), title="승인하기")
    by_title = {
        "내 자산": dash,
        "자산 챗": chat,
        "기록하기": record,
        "승인하기": approve,
    }
    return home, dash, chat, record, approve, by_title


def _render_logged_in_home() -> None:
    user = st.session_state.user
    app_user = st.session_state.app_user or {}
    name = app_user.get("display_name") or (user.email or "회원")
    page_hero("홈", "메뉴를 눌러 내 자산·자산 챗·기록·승인으로 이동하세요.")
    user_chip(str(name), user.email or "")
    _render_auth(logged_in=True)
    pages = st.session_state.get("_cwm_menu_pages") or {}
    pending = int(st.session_state.get("_cwm_pending_ocr") or 0)
    if pending:
        st.info(f"승인 대기 OCR {pending}건이 있습니다.")
    _render_menu_buttons(pages=pages, can_navigate=True, pending_approve=pending)


def main() -> None:
    ensure_persistent_login()
    _handle_oauth_callback()
    _await_sid_cookie_if_needed()

    logged_in = bool(
        st.session_state.get("access_token") and st.session_state.get("user")
    )
    if not logged_in:
        _show_logged_out_home()
        return

    if not _ensure_allowed_and_profile():
        return

    home, dash, chat, record, approve, by_title = _make_pages()
    st.session_state._cwm_menu_pages = by_title

    # Pending OCR badge for home + sidebar
    try:
        from lib.supabase_client import get_user_client
        from lib.ux import pending_ocr_count

        uclient = get_user_client(
            st.session_state.access_token,
            st.session_state.refresh_token,
        )
        st.session_state._cwm_pending_ocr = pending_ocr_count(uclient)
    except Exception:
        st.session_state._cwm_pending_ocr = 0

    pending = int(st.session_state.get("_cwm_pending_ocr") or 0)
    approve_label = f"승인하기 ({pending})" if pending else "승인하기"

    pg = st.navigation([home, dash, chat, record, approve], position="hidden")

    with st.sidebar:
        st.markdown("### 부자뚱")
        st.page_link(home, label="홈", use_container_width=True)
        st.page_link(dash, label="내 자산", use_container_width=True)
        st.page_link(chat, label="자산 챗", use_container_width=True)
        st.page_link(record, label="기록하기", use_container_width=True)
        st.page_link(approve, label=approve_label, use_container_width=True)
        st.divider()
        app_user = st.session_state.app_user or {}
        name = app_user.get("display_name") or (st.session_state.user.email or "")
        st.caption(name)
        if st.button("로그아웃", key="sidebar_logout", use_container_width=True):
            logout_and_clear()
            st.rerun()

    pg.run()


main()
