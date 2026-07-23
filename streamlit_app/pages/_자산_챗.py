"""Page: Asset-grounded free chat with Gemini (session + archived log context)."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth import ensure_profile, require_auth  # noqa: E402
from lib.gemini_client import GeminiError, chat_about_wealth  # noqa: E402
from lib.wealth_context import (  # noqa: E402
    build_wealth_context,
    context_to_prompt_block,
    fetch_recent_chat_logs,
    logs_to_chat_turns,
)
from lib.theme import apply_theme, page_hero, render_bottom_actions  # noqa: E402


st.set_page_config(page_title="자산 챗 · 부자뚱", page_icon="💚", layout="wide")
apply_theme(max_width=1120)


def _reload_context(client) -> None:
    ctx = build_wealth_context(client)
    st.session_state.wealth_ctx_text = context_to_prompt_block(ctx)
    st.session_state.wealth_ctx_meta = {
        "holdings": len(ctx.get("holdings") or []),
        "usdkrw": ctx.get("usdkrw"),
        "approx_investment_usd": ctx.get("approx_investment_usd"),
        "chat_logs": len(ctx.get("recent_chat_logs") or []),
    }


def _hydrate_from_logs(client) -> None:
    """Restore UI turns from DB so cross-session continuity is visible."""
    if st.session_state.get("wealth_chat_hydrated"):
        return
    logs = fetch_recent_chat_logs(client, limit=16)
    turns = logs_to_chat_turns(logs)
    if turns and not st.session_state.get("wealth_chat"):
        st.session_state.wealth_chat = turns
    st.session_state.wealth_chat_hydrated = True


def main() -> None:
    page_hero(
        "자산 챗",
        "내 자산 데이터와 이전 대화를 바탕으로 질문합니다. 숫자는 최신 포트폴리오가 우선입니다.",
    )

    user, client = require_auth()
    ensure_profile(user, client)

    st.session_state.setdefault("wealth_chat", [])
    st.session_state.setdefault("wealth_ctx_text", None)
    st.session_state.setdefault("wealth_chat_hydrated", False)

    _hydrate_from_logs(client)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("자산·로그 컨텍스트 새로고침", type="primary"):
            with st.spinner("DB 로드 중…"):
                _reload_context(client)
            st.success("컨텍스트 갱신됨")
    with col2:
        if st.button("화면 대화만 초기화"):
            st.session_state.wealth_chat = []
            st.session_state.wealth_chat_hydrated = True  # don't auto-reload immediately
            st.rerun()

    if not st.session_state.wealth_ctx_text:
        with st.spinner("첫 컨텍스트 로드…"):
            _reload_context(client)

    meta = st.session_state.get("wealth_ctx_meta") or {}
    st.info(
        f"근거: 보유 {meta.get('holdings', '?')}종 · "
        f"달러원환율 {meta.get('usdkrw', '—')} · "
        f"평가(달러) ≈ {meta.get('approx_investment_usd', '—')} · "
        f"최근 대화 로그 {meta.get('chat_logs', '?')}건"
    )

    with st.expander("컨텍스트 미리보기 (포트폴리오 + 최근 대화 로그)", expanded=False):
        st.code(st.session_state.wealth_ctx_text or "", language="json")

    for msg in st.session_state.wealth_chat:
        with st.chat_message("assistant" if msg["role"] == "model" else "user"):
            st.markdown(msg["content"])

    prompt = st.chat_input("예: 아까 말한 그 종목 비중이 지금 얼마야?")
    if not prompt:
        return

    st.session_state.wealth_chat.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            with st.spinner("생각 중…"):
                # Refresh logs into context each turn so brand-new saves are visible next question
                _reload_context(client)
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.wealth_chat[:-1]
                ]
                answer = chat_about_wealth(
                    prompt,
                    st.session_state.wealth_ctx_text,
                    history=history,
                )
            st.markdown(answer)
            st.session_state.wealth_chat.append({"role": "model", "content": answer})
            try:
                client.table("ai_chat_logs").insert(
                    {
                        "user_id": str(user.id),
                        "user_query": prompt,
                        "ai_response": answer,
                        "context_summary": (st.session_state.wealth_ctx_text or "")[:2000],
                    }
                ).execute()
            except Exception as exc:
                st.caption(f"로그 저장 실패(대화는 유지됨): {exc}")
        except GeminiError as exc:
            st.error(str(exc))
            st.session_state.wealth_chat.pop()
        except Exception as exc:
            st.error(f"채팅 실패: {exc}")
            if st.session_state.wealth_chat and st.session_state.wealth_chat[-1]["role"] == "user":
                st.session_state.wealth_chat.pop()

    render_bottom_actions(enabled=True)


main()
