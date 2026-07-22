"""Load configuration from environment / .env / Streamlit Cloud secrets."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv


def hydrate_env() -> None:
    """Populate os.environ from .env and Streamlit secrets (Cloud)."""
    load_dotenv(override=False)
    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets is None:
            return
        # Flat secrets: KEY = "value"
        for key in secrets:
            try:
                val = secrets[key]
            except Exception:
                continue
            if isinstance(val, dict):
                for sk, sv in val.items():
                    if sv is not None and not os.getenv(str(sk)):
                        os.environ[str(sk)] = str(sv)
            elif val is not None and not os.getenv(str(key)):
                os.environ[str(key)] = str(val)
    except Exception:
        # Outside Streamlit or secrets missing — ignore
        pass


def env(name: str, default: str = "") -> str:
    hydrate_env()
    return (os.getenv(name, default) or default).strip()


@lru_cache(maxsize=1)
def app_base_url() -> str:
    """Canonical public app URL used for OAuth redirect and bookmarks.

    Production: set PUBLIC_APP_URL to the Streamlit Cloud URL, e.g.
    https://couples-wealth.streamlit.app
    """
    hydrate_env()
    # Prefer explicit public URL; STABLE_APP_URL kept as alias for older deploys
    url = env("PUBLIC_APP_URL") or env("STABLE_APP_URL") or "http://localhost:8501"
    return url.rstrip("/")
