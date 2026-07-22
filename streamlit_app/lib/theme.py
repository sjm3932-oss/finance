"""Naver Pay–inspired Streamlit theme (#03C75A)."""

from __future__ import annotations

import streamlit as st

PRIMARY = "#03C75A"
PRIMARY_DARK = "#02B350"
PRIMARY_DEEP = "#019C46"
PRIMARY_SOFT = "#E8F8EF"
PRIMARY_MIST = "#F2FBF6"
INK = "#1A1A1A"
MUTED = "#6B7280"
LINE = "#E5E7EB"
SURFACE = "#FFFFFF"
CANVAS = "#F4F6F5"

# Plotly / chart palette (green-led, ticker colors stay distinct)
CHART_COLORS = [
    PRIMARY,
    "#00A3FF",
    "#FFB800",
    "#FF6B6B",
    "#7C5CFC",
    "#14B8A6",
    "#F97316",
    "#64748B",
]

CHART_LAYOUT = dict(
    margin=dict(l=8, r=8, t=48, b=8),
    height=340,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Pretendard, Noto Sans KR, sans-serif", color=INK, size=13),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    hovermode="x unified",
    colorway=CHART_COLORS,
)


def apply_theme(*, max_width: int = 960) -> None:
    """Inject global Naver Pay–style CSS. Call once per page after set_page_config."""
    st.markdown(
        f"""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');

:root {{
  --np-green: {PRIMARY};
  --np-green-dark: {PRIMARY_DARK};
  --np-green-deep: {PRIMARY_DEEP};
  --np-soft: {PRIMARY_SOFT};
  --np-mist: {PRIMARY_MIST};
  --np-ink: {INK};
  --np-muted: {MUTED};
  --np-line: {LINE};
  --np-surface: {SURFACE};
  --np-canvas: {CANVAS};
}}

html, body, [class*="css"] {{
  font-family: Pretendard, "Noto Sans KR", -apple-system, BlinkMacSystemFont, sans-serif !important;
  color: var(--np-ink);
}}

/* App canvas — soft green mist + subtle grid */
.stApp {{
  background:
    radial-gradient(1200px 480px at 10% -10%, rgba(3,199,90,0.16), transparent 55%),
    radial-gradient(900px 420px at 100% 0%, rgba(3,199,90,0.08), transparent 50%),
    linear-gradient(180deg, #F7FBF8 0%, var(--np-canvas) 42%, #EEF2F0 100%) !important;
}}

.block-container {{
  padding-top: 1.25rem !important;
  padding-bottom: 3rem !important;
  max-width: {max_width}px !important;
}}

/* Sidebar — clean white rail with green active */
section[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, #FFFFFF 0%, #F7FBF8 100%) !important;
  border-right: 1px solid var(--np-line) !important;
}}
section[data-testid="stSidebar"] .stMarkdown p {{
  color: var(--np-muted);
}}
[data-testid="stSidebarNav"] a {{
  border-radius: 12px !important;
  margin: 2px 6px !important;
  padding: 0.55rem 0.75rem !important;
  font-weight: 600 !important;
  transition: background 0.18s ease, color 0.18s ease, transform 0.18s ease;
}}
[data-testid="stSidebarNav"] a:hover {{
  background: var(--np-soft) !important;
  color: var(--np-green-deep) !important;
  transform: translateX(2px);
}}
[data-testid="stSidebarNav"] a[aria-selected="true"] {{
  background: var(--np-green) !important;
  color: #fff !important;
}}

/* Headers */
h1, h2, h3 {{
  letter-spacing: -0.03em !important;
  color: var(--np-ink) !important;
  font-weight: 800 !important;
}}
h1 {{
  font-size: 1.85rem !important;
  margin-bottom: 0.25rem !important;
}}
.stCaption, [data-testid="stCaptionContainer"] {{
  color: var(--np-muted) !important;
}}

/* Primary buttons — Naver Pay CTA */
div.stButton > button,
div.stFormSubmitButton > button,
div.stDownloadButton > button {{
  width: 100%;
  min-height: 3rem;
  border-radius: 14px !important;
  font-weight: 700 !important;
  letter-spacing: -0.02em;
  transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease !important;
}}
div.stButton > button[kind="primary"],
div.stFormSubmitButton > button[kind="primary"],
div.stLinkButton > a[kind="primary"],
button[data-testid="baseButton-primary"] {{
  background: linear-gradient(180deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%) !important;
  border: none !important;
  color: #fff !important;
  box-shadow: 0 8px 20px rgba(3, 199, 90, 0.28) !important;
}}
div.stButton > button[kind="primary"]:hover,
div.stFormSubmitButton > button[kind="primary"]:hover,
button[data-testid="baseButton-primary"]:hover {{
  background: linear-gradient(180deg, {PRIMARY_DARK} 0%, {PRIMARY_DEEP} 100%) !important;
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(3, 199, 90, 0.34) !important;
}}
div.stButton > button[kind="secondary"],
button[data-testid="baseButton-secondary"] {{
  background: #fff !important;
  border: 1.5px solid var(--np-line) !important;
  color: var(--np-ink) !important;
}}
div.stButton > button[kind="secondary"]:hover {{
  border-color: var(--np-green) !important;
  color: var(--np-green-deep) !important;
  background: var(--np-mist) !important;
}}
div.stLinkButton > a {{
  width: 100%;
  min-height: 3rem;
  display: flex !important;
  align-items: center;
  justify-content: center;
  border-radius: 14px !important;
  font-weight: 700 !important;
}}

/* Inputs */
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] > div,
.stTextInput input, .stNumberInput input, .stTextArea textarea {{
  border-radius: 12px !important;
  border-color: var(--np-line) !important;
  background: #fff !important;
}}
div[data-baseweb="input"]:focus-within > div,
div[data-baseweb="select"]:focus-within > div {{
  border-color: var(--np-green) !important;
  box-shadow: 0 0 0 3px rgba(3,199,90,0.15) !important;
}}

/* Metrics — soft white panels */
div[data-testid="stMetric"] {{
  background: var(--np-surface);
  border: 1px solid rgba(3,199,90,0.12);
  border-radius: 16px;
  padding: 1rem 1.1rem;
  box-shadow: 0 6px 18px rgba(26, 26, 26, 0.04);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}}
div[data-testid="stMetric"]:hover {{
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(3, 199, 90, 0.12);
}}
div[data-testid="stMetric"] label {{
  color: var(--np-muted) !important;
  font-weight: 600 !important;
}}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
  color: var(--np-ink) !important;
  font-weight: 800 !important;
  letter-spacing: -0.03em;
}}

/* Tabs */
button[data-baseweb="tab"] {{
  font-weight: 700 !important;
  border-radius: 999px !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
  background: var(--np-soft) !important;
  color: var(--np-green-deep) !important;
}}

/* Expanders / alerts */
details[data-testid="stExpander"] {{
  background: #fff;
  border: 1px solid var(--np-line);
  border-radius: 16px;
  overflow: hidden;
}}
div[data-testid="stAlert"] {{
  border-radius: 14px !important;
}}

/* Dataframes */
div[data-testid="stDataFrame"] {{
  border: 1px solid var(--np-line);
  border-radius: 16px;
  overflow: hidden;
  background: #fff;
}}

/* Chat */
[data-testid="stChatMessage"] {{
  background: #fff;
  border: 1px solid var(--np-line);
  border-radius: 16px;
  padding: 0.75rem 1rem;
}}

/* Brand header block */
.np-hero {{
  position: relative;
  overflow: hidden;
  border-radius: 22px;
  padding: 1.35rem 1.4rem 1.25rem;
  margin: 0 0 1.25rem 0;
  color: #fff;
  background:
    linear-gradient(135deg, {PRIMARY} 0%, {PRIMARY_DEEP} 55%, #018A3D 100%);
  box-shadow: 0 14px 36px rgba(3, 199, 90, 0.28);
  animation: npFadeUp 0.45s ease both;
}}
.np-hero::after {{
  content: "";
  position: absolute;
  right: -40px;
  top: -50px;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: rgba(255,255,255,0.12);
}}
.np-hero::before {{
  content: "";
  position: absolute;
  right: 40px;
  bottom: -60px;
  width: 140px;
  height: 140px;
  border-radius: 50%;
  background: rgba(255,255,255,0.08);
}}
.np-hero-brand {{
  position: relative;
  z-index: 1;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  opacity: 0.92;
  margin-bottom: 0.35rem;
}}
.np-hero-title {{
  position: relative;
  z-index: 1;
  font-size: 1.65rem;
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1.25;
  margin: 0;
}}
.np-hero-sub {{
  position: relative;
  z-index: 1;
  margin-top: 0.45rem;
  font-size: 0.95rem;
  opacity: 0.92;
  font-weight: 500;
}}

.np-section {{
  background: #fff;
  border: 1px solid var(--np-line);
  border-radius: 18px;
  padding: 1.1rem 1.15rem;
  margin: 0 0 1rem 0;
  box-shadow: 0 8px 22px rgba(26,26,26,0.035);
  animation: npFadeUp 0.5s ease both;
}}
.np-section h3 {{
  margin: 0 0 0.65rem 0 !important;
  font-size: 1.05rem !important;
}}

.np-menu-grid {{
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.65rem;
}}
@media (min-width: 720px) {{
  .np-menu-grid {{ grid-template-columns: 1fr 1fr; }}
}}
.np-menu-item {{
  display: flex;
  gap: 0.85rem;
  align-items: flex-start;
  padding: 0.95rem 1rem;
  border-radius: 16px;
  background: var(--np-mist);
  border: 1px solid rgba(3,199,90,0.14);
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}}
.np-menu-item:hover {{
  transform: translateY(-2px);
  background: #fff;
  box-shadow: 0 10px 22px rgba(3,199,90,0.12);
}}
.np-menu-num {{
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: var(--np-green);
  color: #fff;
  font-weight: 800;
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  justify-content: center;
}}
.np-menu-body strong {{
  display: block;
  color: var(--np-ink);
  font-size: 0.98rem;
  letter-spacing: -0.02em;
}}
.np-menu-body span {{
  display: block;
  margin-top: 0.15rem;
  color: var(--np-muted);
  font-size: 0.86rem;
  line-height: 1.4;
}}

.np-user-chip {{
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: #fff;
  border: 1px solid rgba(3,199,90,0.2);
  color: var(--np-ink);
  border-radius: 999px;
  padding: 0.45rem 0.9rem;
  font-weight: 600;
  font-size: 0.9rem;
  margin-bottom: 1rem;
  box-shadow: 0 4px 14px rgba(3,199,90,0.08);
  animation: npFadeUp 0.4s ease both;
}}
.np-user-dot {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--np-green);
  box-shadow: 0 0 0 4px rgba(3,199,90,0.18);
}}

@keyframes npFadeUp {{
  from {{ opacity: 0; transform: translateY(8px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

/* Streamlit chrome tweaks */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{
  background: transparent !important;
}}

@media (max-width: 640px) {{
  h1 {{ font-size: 1.45rem !important; }}
  .np-hero-title {{ font-size: 1.35rem; }}
  .block-container {{ padding-left: 0.9rem !important; padding-right: 0.9rem !important; }}
}}
</style>
""",
        unsafe_allow_html=True,
    )


def page_hero(title: str, subtitle: str = "", brand: str = "부부 자산 마스터") -> None:
    sub = f'<div class="np-hero-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
<div class="np-hero">
  <div class="np-hero-brand">{brand}</div>
  <h1 class="np-hero-title">{title}</h1>
  {sub}
</div>
""",
        unsafe_allow_html=True,
    )


def user_chip(name: str, email: str = "") -> None:
    detail = f" · {email}" if email else ""
    st.markdown(
        f"""
<div class="np-user-chip">
  <span class="np-user-dot"></span>
  <span><strong>{name}</strong>{detail}</span>
</div>
""",
        unsafe_allow_html=True,
    )


def section_start(title: str = "") -> None:
    head = f"<h3>{title}</h3>" if title else ""
    st.markdown(f'<div class="np-section">{head}', unsafe_allow_html=True)


def section_end() -> None:
    st.markdown("</div>", unsafe_allow_html=True)
