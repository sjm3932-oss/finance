"""Page: Asset-grounded free chat with Gemini."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth import ensure_profile, require_auth  # noqa: E402
from lib.gemini_client import GeminiError, chat_about_wealth  # noqa: E402
from lib.wealth_context import build_wealth_context, context_to_prompt_block  # noqa: E402

st.set_page_config(page_title="Wealth Chat", layout="wide")

st.markdown(
    """
<style>
  .block-container { padding-top: 1rem; max-width: 900px; }
  div.stButton > button { width: 100%; min-height: 2.6rem; }
</style>
""",
    unsafe_allow_html=True,
)


def main() -> None:
    st.title("Wealth Chat")
    st.caption("내 자산 데이터만 근거로 하는 Gemini 대화 · 범위 밖 질문은 거절합니다")

    user, client = require_auth()
    ensure_profile(user, client)

    if "wealth_chat" not in st.session_state:
        st.session_state.wealth_chat = []  # [{role, content}]
    if "wealth_ctx_text" not in st.session_state:
        st.session_state.wealth_ctx_text = None

    col1, col2 = st.columns(2)
    with col1:
        if st.button("자산 컨텍스트 새로고침", type="primary"):
            with st.spinner("DB에서 포트폴리오 로드 중…"):
                ctx = build_wealth_context(client)
                st.session_state.wealth_ctx_text = context_to_prompt_block(ctx)
                st.session_state.wealth_ctx_meta = {
                    "holdings": len(ctx.get("holdings") or []),
                    "usdkrw": ctx.get("usdkrw"),
                    "approx_investment_usd": ctx.get("approx_investment_usd"),
                }
            st.success("컨텍스트 갱신됨")
    with col2:
        if st.button("대화 초기화"):
            st.session_state.wealth_chat = []
            st.rerun()

    if not st.session_state.wealth_ctx_text:
        with st.spinner("첫 컨텍스트 로드…"):
            ctx = build_wealth_context(client)
            st.session_state.wealth_ctx_text = context_to_prompt_block(ctx)
            st.session_state.wealth_ctx_meta = {
                "holdings": len(ctx.get("holdings") or []),
                "usdkrw": ctx.get("usdkrw"),
                "approx_investment_usd": ctx.get("approx_investment_usd"),
            }

    meta = st.session_state.get("wealth_ctx_meta") or {}
    st.info(
        f"근거 데이터: 보유 {meta.get('holdings', '?')}종 · "
        f"USD/KRW {meta.get('usdkrw', '—')} · "
        f"평가(USD) ≈ {meta.get('approx_investment_usd', '—')}"
    )

    with st.expander("컨텍스트 미리보기 (전송되는 JSON)", expanded=False):
        st.code(st.session_state.wealth_ctx_text or "", language="json")

    for msg in st.session_state.wealth_chat:
        with st.chat_message("assistant" if msg["role"] == "model" else "user"):
            st.markdown(msg["content"])

    prompt = st.chat_input("예: 지금 순자산이 얼마야? TQQQ 비중이 커?")
    if not prompt:
        return

    st.session_state.wealth_chat.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            with st.spinner("생각 중…"):
                # History for model: prior turns only (current user msg passed separately)
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
            # Persist archive
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
            st.session_state.wealth_chat.pop()  # remove failed user turn display consistency
        except Exception as exc:
            st.error(f"채팅 실패: {exc}")
            if st.session_state.wealth_chat and st.session_state.wealth_chat[-1]["role"] == "user":
                st.session_state.wealth_chat.pop()


main()
