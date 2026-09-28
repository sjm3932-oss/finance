"""Deprecated Streamlit entry — production is Next.js on Vercel only."""

from __future__ import annotations

import streamlit as st

VERCEL_APP = "https://richddoong.vercel.app"

st.set_page_config(page_title="부자뚱 (이동됨)", page_icon="💚", layout="centered")
st.markdown(
    f"""
<div style="max-width:420px;margin:4rem auto;padding:1.5rem;border:1px solid #E5E7EB;
border-radius:16px;font-family:system-ui,sans-serif;text-align:center">
  <div style="color:#03C75A;font-weight:800;margin-bottom:0.5rem">부자뚱</div>
  <h1 style="font-size:1.35rem;margin:0 0 0.75rem">앱 주소가 변경되었습니다</h1>
  <p style="color:#6B7280;line-height:1.5;margin:0 0 1.25rem">
    Streamlit 호스트는 더 이상 쓰지 않습니다.<br/>
    아래 고정 주소로 이동하세요.
  </p>
  <a href="{VERCEL_APP}" target="_self"
     style="display:block;padding:0.9rem 1rem;border-radius:14px;background:#03C75A;
     color:#fff;font-weight:700;text-decoration:none">
    {VERCEL_APP.replace("https://", "")} 열기
  </a>
</div>
<meta http-equiv="refresh" content="0;url={VERCEL_APP}" />
""",
    unsafe_allow_html=True,
)
st.stop()
