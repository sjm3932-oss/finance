"""자산 챗 + 브리핑/알림 (사이드바 메뉴)."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth import ensure_profile, require_auth  # noqa: E402
from lib.gemini_client import GeminiError, chat_about_wealth  # noqa: E402
from lib.jobs import briefing_text_from_result, invoke_edge  # noqa: E402
from lib.push_ui import render_push_subscribe  # noqa: E402
from lib.theme import apply_theme, page_hero  # noqa: E402
from lib.wealth_context import (  # noqa: E402
    build_wealth_context,
    context_to_prompt_block,
    fetch_recent_chat_logs,
    logs_to_chat_turns,
)

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
    if st.session_state.get("wealth_chat_hydrated"):
        return
    logs = fetch_recent_chat_logs(client, limit=16)
    turns = logs_to_chat_turns(logs)
    if turns and not st.session_state.get("wealth_chat"):
        st.session_state.wealth_chat = turns
    st.session_state.wealth_chat_hydrated = True


def _append_assistant(client, user, text: str, *, user_query: str) -> None:
    st.session_state.wealth_chat.append({"role": "model", "content": text})
    try:
        client.table("ai_chat_logs").insert(
            {
                "user_id": str(user.id),
                "user_query": user_query,
                "ai_response": text,
                "context_summary": (st.session_state.wealth_ctx_text or "")[:2000],
            }
        ).execute()
    except Exception:
        pass


def main() -> None:
    page_hero(
        "자산 챗",
        "자산 데이터로 질문하고, 브리핑·알림도 여기서 받습니다.",
    )

    user, client = require_auth()
    ensure_profile(user, client)
    access = st.session_state.get("access_token") or ""

    st.session_state.setdefault("wealth_chat", [])
    st.session_state.setdefault("wealth_ctx_text", None)
    st.session_state.setdefault("wealth_chat_hydrated", False)
    _hydrate_from_logs(client)

    b1, b2, b3 = st.columns(3)
    with b1:
        want_brief = st.button("오늘 브리핑 받기", type="primary", use_container_width=True)
    with b2:
        if st.button("컨텍스트 새로고침", use_container_width=True):
            with st.spinner("DB 로드 중…"):
                _reload_context(client)
            st.success("컨텍스트 갱신됨")
    with b3:
        if st.button("화면 대화 초기화", use_container_width=True):
            st.session_state.wealth_chat = []
            st.session_state.wealth_chat_hydrated = True
            st.rerun()

    with st.expander("알림 구독 · 시세/백업", expanded=False):
        st.caption("푸시 알림을 구독하면 브리핑이 폰으로도 옵니다.")
        render_push_subscribe(user_id=str(user.id), access_token=access)
        c1, c2, c3 = st.columns(3)
        if c1.button("시세 갱신", key="chat_refresh_px"):
            st.json(invoke_edge("refresh-prices", access))
        if c2.button("야간 백업", key="chat_backup"):
            st.json(invoke_edge("nightly-backup", access))
        if c3.button("오늘 스냅샷", key="chat_snap"):
            try:
                st.success(client.rpc("compute_daily_snapshot").execute().data)
            except Exception as exc:
                st.error(str(exc))

    if want_brief:
        st.session_state.wealth_chat.append(
            {"role": "user", "content": "오늘 아침 브리핑 보여줘"}
        )
        with st.spinner("브리핑 생성 중…"):
            result = invoke_edge("morning-briefing", access)
            text = briefing_text_from_result(result)
            if not text:
                try:
                    if not st.session_state.wealth_ctx_text:
                        _reload_context(client)
                    text = chat_about_wealth(
                        "오늘 자산 현황을 3~6문장으로 아침 브리핑처럼 요약해줘. "
                        "순자산·투자·부채와 오늘 체크할 액션 1개를 포함해.",
                        st.session_state.wealth_ctx_text or "",
                        history=[],
                    )
                except Exception as exc:
                    text = f"브리핑을 만들지 못했습니다: {exc}\n\n응답: `{result}`"
            _append_assistant(client, user, text, user_query="morning_briefing")
        st.rerun()

    if not st.session_state.wealth_ctx_text:
        with st.spinner("첫 컨텍스트 로드…"):
            _reload_context(client)

    meta = st.session_state.get("wealth_ctx_meta") or {}
    st.info(
        f"근거: 보유 {meta.get('holdings', '?')}종 · "
        f"달러원환율 {meta.get('usdkrw', '—')} · "
        f"평가(달러) ≈ {meta.get('approx_investment_usd', '—')}"
    )

    for msg in st.session_state.wealth_chat:
        with st.chat_message("assistant" if msg["role"] == "model" else "user"):
            st.markdown(msg["content"])

    prompt = st.chat_input("예: 우리 순자산이 얼마야?")
    if not prompt:
        return

    st.session_state.wealth_chat.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            with st.spinner("생각 중…"):
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
            _append_assistant(client, user, answer, user_query=prompt)
        except GeminiError as exc:
            st.error(str(exc))
            st.session_state.wealth_chat.pop()
        except Exception as exc:
            st.error(f"채팅 실패: {exc}")
            if st.session_state.wealth_chat and st.session_state.wealth_chat[-1]["role"] == "user":
                st.session_state.wealth_chat.pop()


main()
