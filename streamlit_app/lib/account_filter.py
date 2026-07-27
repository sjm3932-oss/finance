"""Shared brokerage-account filter for 내 자산 tabs."""

from __future__ import annotations

import streamlit as st


def account_map(client) -> dict[str, str]:
    rows = client.table("accounts").select("id,institution").execute().data or []
    return {str(a["id"]): (a.get("institution") or "계좌") for a in rows}


def account_options(client) -> list[str]:
    names = sorted({n for n in account_map(client).values() if n})
    return ["전체"] + names


def account_ids_for_label(client, label: str) -> list[str] | None:
    """None = 전체 (no filter). Otherwise list of account UUIDs."""
    if not label or label == "전체":
        return None
    amap = account_map(client)
    ids = [aid for aid, name in amap.items() if name == label]
    return ids


def _segment_select(options: list[str], *, key: str) -> str:
    """Toss-like pill segments instead of a selectbox."""
    current = st.session_state.get(key)
    if current not in options:
        st.session_state[key] = options[0] if options else "전체"
        current = st.session_state[key]

    st.markdown(
        '<div class="np-account-seg-label">계좌</div>',
        unsafe_allow_html=True,
    )

    # Prefer native segmented_control / pills when available
    if hasattr(st, "segmented_control"):
        chosen = st.segmented_control(
            "계좌",
            options,
            key=key,
            label_visibility="collapsed",
            default=current if current in options else (options[0] if options else None),
        )
        if chosen is None:
            return str(st.session_state.get(key) or "전체")
        return str(chosen)

    if hasattr(st, "pills"):
        chosen = st.pills(
            "계좌",
            options,
            key=key,
            label_visibility="collapsed",
            default=current if current in options else (options[0] if options else None),
        )
        if chosen is None:
            return str(st.session_state.get(key) or "전체")
        return str(chosen)

    # Fallback: button row
    cols = st.columns(len(options) if options else 1)
    for i, opt in enumerate(options):
        with cols[i]:
            active = opt == current
            if st.button(
                opt,
                key=f"{key}__btn_{i}",
                type="primary" if active else "secondary",
                use_container_width=True,
            ):
                st.session_state[key] = opt
                st.rerun()
    return str(st.session_state.get(key) or "전체")


def render_account_selector(
    client, *, key: str = "dash_account_filter", sticky: bool = True
) -> str:
    options = account_options(client)
    current = st.session_state.get(key)
    if current not in options:
        st.session_state[key] = "전체"

    def _select() -> str:
        return _segment_select(options, key=key)

    if not sticky:
        return _select()

    with st.container():
        st.markdown('<span class="np-sticky-marker"></span>', unsafe_allow_html=True)
        return _select()


def filter_df_by_account_ids(df, account_ids: list[str] | None, col: str = "account_id"):
    """Filter a DataFrame by account_id column. None ids → no filter."""
    if account_ids is None or df is None or getattr(df, "empty", True):
        return df
    if col not in df.columns:
        return df.iloc[0:0].copy()
    ids = {str(a) for a in account_ids}
    return df[df[col].astype(str).isin(ids)].copy()
