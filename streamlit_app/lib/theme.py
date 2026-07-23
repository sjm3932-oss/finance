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

# Title styling kept separate so CHART_LAYOUT never ships a ``title`` key —
# unpacking chart_layout() next to title=... must not collide.
TITLE_DEFAULTS = dict(
    font=dict(size=14, color=INK, family="Pretendard, Noto Sans KR, sans-serif"),
    x=0,
    xanchor="left",
    y=0.98,
    yanchor="top",
    pad=dict(t=0, b=12, l=0, r=0),
)

CHART_LAYOUT = dict(
    margin=dict(l=8, r=8, t=24, b=56),
    height=260,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Pretendard, Noto Sans KR, sans-serif", color=INK, size=11),
    legend=dict(
        orientation="h",
        yanchor="top",
        y=-0.18,
        x=0,
        xanchor="left",
        font=dict(size=10),
        bgcolor="rgba(0,0,0,0)",
    ),
    hovermode="x unified",
    colorway=CHART_COLORS,
    autosize=True,
    dragmode=False,
)


def chart_layout(height: int = 300, *, with_title: bool = False, **extra) -> dict:
    """Safe defaults so title / legend / plot never overlap.

    Prefer ``fig.update_layout(chart_layout(..., title="..."))`` (one dict).
    Never puts a bare title into the base dict unless ``title`` is in ``extra``.
    """
    layout = {**CHART_LAYOUT, "height": height}
    # Extra headroom when Plotly draws its own title
    if with_title or extra.get("title"):
        layout["margin"] = {**layout["margin"], "t": 44}
        layout["height"] = max(height, 280)
    layout.update(extra)
    # String titles → styled title dict; leave dict titles as-is
    if "title" in layout and isinstance(layout["title"], str):
        layout["title"] = {**TITLE_DEFAULTS, "text": layout["title"]}
    # Keep legend under the plot even if caller overrides partially
    leg = {**CHART_LAYOUT["legend"], **(extra.get("legend") or {})}
    if "y" not in (extra.get("legend") or {}):
        leg["y"] = -0.18
        leg["yanchor"] = "top"
    layout["legend"] = leg
    # Belt-and-suspenders: never leave an accidental duplicate-prone empty title
    if "title" in layout and layout["title"] in (None, "", {}):
        layout.pop("title", None)
    return layout


def apply_chart_layout(fig, height: int = 300, *, title: str | None = None, **extra) -> None:
    """Apply layout as a single dict — avoids title kwarg collisions."""
    kwargs = dict(extra)
    if title is not None:
        kwargs["title"] = title
    fig.update_layout(chart_layout(height, with_title=bool(title), **kwargs))


def show_plotly(fig, *, key: str | None = None) -> None:
    """Render Plotly figure with spacing that avoids title/legend collisions.

    Drag / box / scroll zoom are always disabled — use period radios instead.
    """
    has_title = bool(getattr(fig.layout, "title", None) and getattr(fig.layout.title, "text", None))
    has_y2 = bool(getattr(fig.layout, "yaxis2", None) and fig.layout.yaxis2)
    height = int(fig.layout.height or 300) if fig.layout.height else 300
    if has_y2:
        height = max(height, 340)
    base = chart_layout(height=height, with_title=has_title)
    margin = dict(base["margin"])
    if has_y2:
        margin["b"] = max(margin.get("b", 88), 100)
        margin["r"] = max(margin.get("r", 12), 48)
    fig.update_layout(
        margin=margin,
        legend=base["legend"],
        paper_bgcolor=base["paper_bgcolor"],
        plot_bgcolor=base["plot_bgcolor"],
        font=base["font"],
        autosize=True,
        hovermode=base.get("hovermode", "x unified"),
        height=height,
        dragmode=False,
    )
    # Lock every cartesian axis so pinch/drag cannot zoom
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    if has_title:
        # Restyle without rebuilding title=dict(**defaults, pad=...) —
        # Plotly merges into the existing Title and duplicate pad blows up.
        fig.layout.title.font = TITLE_DEFAULTS["font"]
        fig.layout.title.x = TITLE_DEFAULTS["x"]
        fig.layout.title.xanchor = TITLE_DEFAULTS["xanchor"]
        fig.layout.title.y = TITLE_DEFAULTS["y"]
        fig.layout.title.yanchor = TITLE_DEFAULTS["yanchor"]
        fig.layout.title.pad = dict(t=0, b=14, l=0, r=0)
    kwargs = {
        "use_container_width": True,
        "config": {
            "responsive": True,
            "displayModeBar": False,
            "scrollZoom": False,
            "doubleClick": False,
            "showTips": False,
            "modeBarButtonsToRemove": [
                "zoom2d",
                "zoomIn2d",
                "zoomOut2d",
                "pan2d",
                "select2d",
                "lasso2d",
                "autoScale2d",
                "resetScale2d",
            ],
        },
    }
    if key:
        kwargs["key"] = key
    st.plotly_chart(fig, **kwargs)


def apply_theme(*, max_width: int = 1120) -> None:
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
  -webkit-text-size-adjust: 100%;
  text-size-adjust: 100%;
}}

.stApp {{
  background:
    radial-gradient(1200px 480px at 10% -10%, rgba(3,199,90,0.16), transparent 55%),
    radial-gradient(900px 420px at 100% 0%, rgba(3,199,90,0.08), transparent 50%),
    linear-gradient(180deg, #F7FBF8 0%, var(--np-canvas) 42%, #EEF2F0 100%) !important;
}}

.block-container {{
  padding-top: clamp(0.45rem, 1.5vw, 0.85rem) !important;
  padding-bottom: clamp(1.2rem, 3vw, 2.2rem) !important;
  padding-left: clamp(0.65rem, 2.5vw, 1.5rem) !important;
  padding-right: clamp(0.65rem, 2.5vw, 1.5rem) !important;
  max-width: min({max_width}px, 100%) !important;
  width: 100% !important;
}}

/* Toss-like density: less vertical whitespace between blocks */
div[data-testid="stVerticalBlock"] > div {{
  gap: 0.35rem !important;
}}
div[data-testid="stHorizontalBlock"] {{
  gap: 0.65rem !important;
}}
hr {{
  margin: 0.45rem 0 !important;
  border: none !important;
  border-top: 1px solid var(--np-line) !important;
}}

section[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, #FFFFFF 0%, #F7FBF8 100%) !important;
  border-right: 1px solid var(--np-line) !important;
}}
[data-testid="stSidebarNav"] a {{
  border-radius: 12px !important;
  margin: 2px 6px !important;
  padding: 0.55rem 0.75rem !important;
  font-weight: 600 !important;
  font-size: clamp(0.85rem, 1.6vw, 0.95rem) !important;
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

h1, h2, h3, h4 {{
  letter-spacing: -0.03em !important;
  color: var(--np-ink) !important;
  font-weight: 800 !important;
  line-height: 1.25 !important;
  word-break: keep-all;
}}
h1 {{ font-size: clamp(1.25rem, 4.2vw, 1.85rem) !important; margin-bottom: 0.25rem !important; }}
h2 {{ font-size: clamp(1.1rem, 3.2vw, 1.4rem) !important; }}
h3 {{ font-size: clamp(1rem, 2.8vw, 1.2rem) !important; }}
p, li, label, .stMarkdown {{
  font-size: clamp(0.88rem, 2.2vw, 1rem) !important;
  line-height: 1.5 !important;
}}
.stCaption, [data-testid="stCaptionContainer"] {{
  color: var(--np-muted) !important;
  font-size: clamp(0.78rem, 2vw, 0.9rem) !important;
}}

div.stButton > button,
div.stFormSubmitButton > button,
div.stDownloadButton > button {{
  width: 100%;
  min-height: clamp(2.6rem, 7vw, 3rem);
  border-radius: 14px !important;
  font-weight: 700 !important;
  font-size: clamp(0.88rem, 2.4vw, 1rem) !important;
  letter-spacing: -0.02em;
  transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease !important;
  white-space: nowrap;
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
/* Active subnav look */
div.stButton > button[kind="primary"].np-active,
div[data-testid="column"] button[kind="primary"] {{
  box-shadow: 0 8px 20px rgba(3, 199, 90, 0.28) !important;
}}
div.stLinkButton > a {{
  width: 100%;
  min-height: clamp(2.6rem, 7vw, 3rem);
  display: flex !important;
  align-items: center;
  justify-content: center;
  border-radius: 14px !important;
  font-weight: 700 !important;
}}

div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] > div,
.stTextInput input, .stNumberInput input, .stTextArea textarea {{
  border-radius: 12px !important;
  border-color: var(--np-line) !important;
  background: #fff !important;
  font-size: clamp(0.88rem, 2.2vw, 1rem) !important;
}}
div[data-baseweb="input"]:focus-within > div,
div[data-baseweb="select"]:focus-within > div {{
  border-color: var(--np-green) !important;
  box-shadow: 0 0 0 3px rgba(3,199,90,0.15) !important;
}}

div[data-testid="stMetric"] {{
  background: #fff;
  border: 1px solid var(--np-line);
  border-radius: 14px;
  padding: 0.55rem 0.75rem 0.6rem !important;
  box-shadow: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
  height: 100%;
}}
div[data-testid="stMetric"]:hover {{
  transform: none;
  border-color: rgba(3,199,90,0.35);
  box-shadow: 0 6px 16px rgba(3, 199, 90, 0.08);
}}
div[data-testid="stMetric"] label {{
  color: var(--np-muted) !important;
  font-weight: 600 !important;
  font-size: 0.72rem !important;
}}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
  color: var(--np-ink) !important;
  font-weight: 800 !important;
  letter-spacing: -0.04em;
  font-size: clamp(1rem, 2.6vw, 1.28rem) !important;
  word-break: break-word;
}}

div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
  gap: 0.1rem !important;
  border-bottom: 1px solid var(--np-line) !important;
  overflow-x: auto !important;
  flex-wrap: nowrap !important;
}}
button[data-baseweb="tab"] {{
  font-weight: 700 !important;
  border-radius: 0 !important;
  font-size: 0.9rem !important;
  padding: 0.5rem 0.8rem !important;
  color: var(--np-muted) !important;
  background: transparent !important;
  border-bottom: 2px solid transparent !important;
  white-space: nowrap !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
  background: transparent !important;
  color: var(--np-ink) !important;
  border-bottom: 2px solid var(--np-green) !important;
}}
div[data-testid="stTabs"] [data-baseweb="tab-panel"] {{
  padding-top: 0.7rem !important;
}}

div[data-testid="stRadio"] > div {{
  gap: 0.3rem !important;
  flex-wrap: wrap !important;
}}
div[data-testid="stRadio"] label {{
  background: #fff !important;
  border: 1px solid var(--np-line) !important;
  border-radius: 999px !important;
  padding: 0.22rem 0.7rem !important;
}}

details[data-testid="stExpander"] {{
  background: #fff;
  border: 1px solid var(--np-line);
  border-radius: 16px;
  overflow: hidden;
}}
div[data-testid="stAlert"] {{ border-radius: 14px !important; }}
div[data-testid="stDataFrame"] {{
  border: 1px solid var(--np-line);
  border-radius: 16px;
  overflow: hidden;
  background: #fff;
  max-width: 100%;
}}
[data-testid="stChatMessage"] {{
  background: #fff;
  border: 1px solid var(--np-line);
  border-radius: 16px;
  padding: 0.75rem 1rem;
}}

div[data-testid="stPlotlyChart"],
.js-plotly-plot, .plotly, .plot-container {{
  width: 100% !important;
  max-width: 100% !important;
}}
div[data-testid="stPlotlyChart"] {{
  margin: 0.15rem 0 0.55rem 0 !important;
  padding-top: 0 !important;
  overflow: visible !important;
}}
/* Streamlit section titles above charts — keep clear gap */
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
.stMarkdown h4, .stMarkdown h5, .stMarkdown h6,
[data-testid="stMarkdownContainer"] h5 {{
  margin-top: 0.35rem !important;
  margin-bottom: 0.35rem !important;
  line-height: 1.3 !important;
}}
/* Avoid stacked title+chart feeling cramped inside columns */
div[data-testid="column"] div[data-testid="stPlotlyChart"] {{
  margin-bottom: 0.65rem !important;
}}
div[data-testid="stVerticalBlockBorderWrapper"] {{
  overflow: visible !important;
}}

.np-hero {{
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  padding: 0.85rem 1rem;
  margin: 0 0 0.65rem 0;
  color: #fff;
  background: linear-gradient(135deg, {PRIMARY} 0%, {PRIMARY_DEEP} 55%, #018A3D 100%);
  box-shadow: 0 10px 28px rgba(3, 199, 90, 0.22);
  animation: npFadeUp 0.35s ease both;
}}
.np-hero.np-hero-compact {{
  padding: 0.65rem 0.9rem;
  margin-bottom: 0.5rem;
  border-radius: 14px;
}}
.np-hero.np-hero-compact .np-hero-title {{
  font-size: 1.15rem !important;
  margin: 0 !important;
}}
.np-hero.np-hero-compact .np-hero-sub {{
  margin-top: 0.15rem;
  opacity: 0.9;
  font-size: 0.82rem;
}}
.np-hero.np-hero-compact .np-hero-brand {{
  font-size: 0.72rem;
  margin-bottom: 0.1rem;
}}
.np-hold-list {{
  background: #fff;
  border: 1px solid var(--np-line);
  border-radius: 16px;
  overflow: hidden;
  margin: 0.35rem 0 0.75rem;
}}
.np-hold-row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--np-line);
}}
.np-hold-row:last-child {{ border-bottom: none; }}
.np-hold-left {{ min-width: 0; }}
.np-hold-ticker {{
  font-weight: 800;
  font-size: 0.98rem;
  letter-spacing: -0.03em;
  color: var(--np-ink);
}}
.np-hold-meta {{
  color: var(--np-muted);
  font-size: 0.78rem;
  margin-top: 0.12rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.np-hold-right {{ text-align: right; flex-shrink: 0; }}
.np-hold-value {{
  font-weight: 800;
  font-size: 0.98rem;
  letter-spacing: -0.03em;
}}
.np-hold-ret {{
  font-size: 0.8rem;
  font-weight: 700;
  margin-top: 0.1rem;
}}
.np-hold-ret.up {{ color: #E11D48; }}
.np-hold-ret.down {{ color: #2563EB; }}
.np-hold-ret.flat {{ color: var(--np-muted); }}

.np-networth {{
  background: #fff;
  border: 1px solid var(--np-line);
  border-radius: 16px;
  padding: 0.9rem 1rem;
  margin-bottom: 0.55rem;
}}
.np-networth-label {{
  color: var(--np-muted);
  font-size: 0.78rem;
  font-weight: 600;
}}
.np-networth-value {{
  font-size: clamp(1.55rem, 4vw, 2rem);
  font-weight: 800;
  letter-spacing: -0.045em;
  color: var(--np-ink);
  line-height: 1.15;
  margin-top: 0.15rem;
}}
.np-networth-sub {{
  color: var(--np-muted);
  font-size: 0.8rem;
  margin-top: 0.25rem;
}}
.np-hero::after {{
  content: "";
  position: absolute;
  right: -40px; top: -50px;
  width: clamp(100px, 28vw, 180px); height: clamp(100px, 28vw, 180px);
  border-radius: 50%;
  background: rgba(255,255,255,0.12);
}}
.np-hero-brand {{
  position: relative; z-index: 1;
  font-size: clamp(0.72rem, 2vw, 0.82rem);
  font-weight: 700; letter-spacing: 0.04em; opacity: 0.92; margin-bottom: 0.35rem;
}}
.np-hero-title {{
  position: relative; z-index: 1;
  font-size: clamp(1.2rem, 4.5vw, 1.7rem) !important;
  font-weight: 800; letter-spacing: -0.04em; line-height: 1.25; margin: 0;
  color: #fff !important;
}}
.np-hero-sub {{
  position: relative; z-index: 1;
  margin-top: 0.45rem;
  font-size: clamp(0.82rem, 2.5vw, 0.98rem);
  opacity: 0.92; font-weight: 500;
}}

.np-section {{
  background: #fff;
  border: 1px solid var(--np-line);
  border-radius: clamp(14px, 2.5vw, 18px);
  padding: clamp(0.85rem, 2.5vw, 1.15rem);
  margin: 0 0 1rem 0;
  box-shadow: 0 8px 22px rgba(26,26,26,0.035);
  animation: npFadeUp 0.5s ease both;
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
  display: flex; gap: 0.85rem; align-items: flex-start;
  padding: 0.95rem 1rem; border-radius: 16px;
  background: var(--np-mist); border: 1px solid rgba(3,199,90,0.14);
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}}
.np-menu-item:hover {{
  transform: translateY(-2px); background: #fff;
  box-shadow: 0 10px 22px rgba(3,199,90,0.12);
}}
.np-menu-num {{
  flex: 0 0 auto; width: 28px; height: 28px; border-radius: 999px;
  background: var(--np-green); color: #fff; font-weight: 800; font-size: 0.8rem;
  display: flex; align-items: center; justify-content: center;
}}
.np-menu-body strong {{
  display: block; color: var(--np-ink);
  font-size: clamp(0.92rem, 2.4vw, 0.98rem); letter-spacing: -0.02em;
}}
.np-menu-body span {{
  display: block; margin-top: 0.15rem; color: var(--np-muted);
  font-size: clamp(0.8rem, 2.1vw, 0.86rem); line-height: 1.4;
}}
.np-user-chip {{
  display: inline-flex; align-items: center; gap: 0.5rem;
  background: #fff; border: 1px solid rgba(3,199,90,0.2);
  color: var(--np-ink); border-radius: 999px;
  padding: 0.45rem 0.9rem; font-weight: 600;
  font-size: clamp(0.8rem, 2.2vw, 0.9rem);
  margin-bottom: 1rem;
  box-shadow: 0 4px 14px rgba(3,199,90,0.08);
  max-width: 100%; flex-wrap: wrap;
}}
.np-user-dot {{
  width: 8px; height: 8px; border-radius: 50%; background: var(--np-green);
  box-shadow: 0 0 0 4px rgba(3,199,90,0.18);
}}

.np-subnav {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.5rem;
  margin: 0 0 1rem 0;
}}
@media (max-width: 640px) {{
  .np-subnav {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
}}

@keyframes npFadeUp {{
  from {{ opacity: 0; transform: translateY(8px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent !important; }}

/* Hide Streamlit chrome (toolbar / status / decoration) */
div[data-testid="stToolbar"],
div[data-testid="stDecoration"],
div[data-testid="stStatusWidget"] {{
  visibility: hidden !important;
  height: 0 !important;
  position: fixed !important;
}}
/* Community Cloud / viewer badge (bottom-right). May not cover host overlay. */
a[href*="streamlit.io"],
a[href*="streamlit.app"][target="_blank"],
div[class*="viewerBadge"],
div[data-testid="stBaseButton-headerNoPadding"] {{
  display: none !important;
  visibility: hidden !important;
  pointer-events: none !important;
}}

/* Home clickable menu rows */
.np-home-menu div.stButton > button {{
  justify-content: flex-start !important;
  text-align: left !important;
  white-space: normal !important;
  line-height: 1.35 !important;
  min-height: 3.2rem !important;
  padding: 0.85rem 1.1rem !important;
  margin-bottom: 0.35rem;
}}

/* Wrap metric / button rows on narrow screens */
@media (max-width: 720px) {{
  div[data-testid="stHorizontalBlock"] {{
    flex-wrap: wrap !important;
    row-gap: 0.55rem !important;
  }}
  div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {{
    min-width: calc(50% - 0.4rem) !important;
    flex: 1 1 calc(50% - 0.4rem) !important;
  }}
}}
@media (max-width: 420px) {{
  div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {{
    min-width: 100% !important;
    flex: 1 1 100% !important;
  }}
}}

</style>
""",
        unsafe_allow_html=True,
    )


def render_bottom_actions(*, enabled: bool = True) -> None:
    """Deprecated — sidebar navigation replaced floating buttons."""
    return


def page_hero(
    title: str,
    subtitle: str = "",
    brand: str = "부자뚱",
    *,
    compact: bool = False,
) -> None:
    sub = f'<div class="np-hero-sub">{subtitle}</div>' if subtitle else ""
    cls = "np-hero np-hero-compact" if compact else "np-hero"
    st.markdown(
        f"""
<div class="{cls}">
  <div class="np-hero-brand">{brand}</div>
  <h1 class="np-hero-title">{title}</h1>
  {sub}
</div>
""",
        unsafe_allow_html=True,
    )


def networth_banner(label: str, value: str, sub: str = "") -> None:
    """Toss-style large net-worth strip."""
    sub_html = f'<div class="np-networth-sub">{sub}</div>' if sub else ""
    st.markdown(
        f"""
<div class="np-networth">
  <div class="np-networth-label">{label}</div>
  <div class="np-networth-value">{value}</div>
  {sub_html}
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


def render_subnav(options: list[str], state_key: str = "dash_view", default: str | None = None) -> str:
    """Segmented control via buttons; returns the selected label."""
    if default is None:
        default = options[0]
    if st.session_state.get(state_key) not in options:
        st.session_state[state_key] = default

    cols = st.columns(len(options), gap="small")
    for i, label in enumerate(options):
        active = st.session_state[state_key] == label
        with cols[i]:
            if st.button(
                label,
                key=f"{state_key}_{label}",
                type="primary" if active else "secondary",
                use_container_width=True,
            ):
                if not active:
                    st.session_state[state_key] = label
                    st.rerun()
    return st.session_state[state_key]
