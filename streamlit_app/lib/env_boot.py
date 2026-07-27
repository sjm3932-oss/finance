"""Load configuration from environment / .env / Streamlit Cloud secrets."""

from __future__ import annotations

import os

from dotenv import load_dotenv

_EPHEMERAL_HOST_MARKERS = (
    "pinggy",
    "trycloudflare.com",
    "lhr.life",
    "loca.lt",
    "ngrok",
    "app-gateway",
    "localhost",
    "127.0.0.1",
)


def hydrate_env() -> None:
    """Populate os.environ from .env and Streamlit secrets (Cloud).

    Streamlit Cloud Secrets win over any pre-set env for the same key so a
    wrong tunnel URL baked into the environment cannot override production.
    """
    load_dotenv(override=False)
    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets is None:
            return
        for key in secrets:
            try:
                val = secrets[key]
            except Exception:
                continue
            if isinstance(val, dict):
                for sk, sv in val.items():
                    if sv is not None:
                        os.environ[str(sk)] = str(sv)
            elif val is not None:
                os.environ[str(key)] = str(val)
    except Exception:
        # Outside Streamlit or secrets missing — ignore
        pass


def env(name: str, default: str = "") -> str:
    hydrate_env()
    return (os.getenv(name, default) or default).strip()


def is_ephemeral_app_url(url: str) -> bool:
    u = (url or "").lower()
    return any(m in u for m in _EPHEMERAL_HOST_MARKERS)


def _host_from_streamlit() -> str:
    """When the user is already on *.streamlit.app, use that host for OAuth."""
    try:
        import streamlit as st

        headers = getattr(getattr(st, "context", None), "headers", None) or {}
        host = str(headers.get("Host") or headers.get("host") or "").split(",")[0].strip()
        if host.endswith(".streamlit.app"):
            return f"https://{host}"
    except Exception:
        pass
    return ""


def app_base_url() -> str:
    """Canonical public app URL used for OAuth redirect and bookmarks.

    Priority:
    1) Live Host header when on Streamlit Community Cloud (*.streamlit.app)
    2) PUBLIC_APP_URL / STABLE_APP_URL from Secrets / .env
    3) localhost fallback
    """
    hydrate_env()
    host_url = _host_from_streamlit()
    if host_url:
        return host_url.rstrip("/")

    url = env("PUBLIC_APP_URL") or env("STABLE_APP_URL") or "http://localhost:8501"
    return url.rstrip("/")
