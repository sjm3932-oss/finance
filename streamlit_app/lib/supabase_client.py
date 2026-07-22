"""Supabase client helpers for Couples Wealth Master."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv(override=False)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://lsqkixysysfhywipmrky.supabase.co").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
ALLOWED_EMAILS = {
    e.strip().lower()
    for e in os.getenv("ALLOWED_EMAILS", "").split(",")
    if e.strip()
}


def get_public_app_url() -> str:
    """Live Streamlit origin (tunnel). Prefer for asset absolute links."""
    load_dotenv(override=True)
    return os.getenv("PUBLIC_APP_URL", "http://localhost:8501").rstrip("/")


def get_stable_app_url() -> str:
    """Stable entry/OAuth redirect (Supabase Edge gateway). Never a trycloudflare host."""
    load_dotenv(override=True)
    return os.getenv(
        "STABLE_APP_URL",
        "https://lsqkixysysfhywipmrky.supabase.co/functions/v1/app-gateway",
    ).rstrip("/")


# Back-compat for importers; prefer getters.
PUBLIC_APP_URL = get_public_app_url()
STABLE_APP_URL = get_stable_app_url()


class ConfigError(RuntimeError):
    pass


def require_env() -> None:
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_ANON_KEY:
        missing.append("SUPABASE_ANON_KEY")
    if missing:
        raise ConfigError(
            "Missing required env vars: " + ", ".join(missing)
            + ". Copy .env.example to .env and fill in secrets."
        )


@lru_cache(maxsize=1)
def get_anon_client() -> Client:
    require_env()
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def get_user_client(access_token: str, refresh_token: str | None = None) -> Client:
    """Return a client authenticated as the current user (RLS applies)."""
    client = get_anon_client()
    if refresh_token:
        client.auth.set_session(access_token, refresh_token)
    else:
        # Fallback: attach bearer for PostgREST/Storage calls
        client.postgrest.auth(access_token)
    return client


def get_service_client() -> Client:
    """Service-role client — use only for bootstrap tasks, never in browser."""
    require_env()
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise ConfigError("SUPABASE_SERVICE_ROLE_KEY is required for service operations")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def is_email_allowed(email: str | None) -> bool:
    if not email:
        return False
    if not ALLOWED_EMAILS:
        # Fail closed when allow-list is empty
        return False
    return email.strip().lower() in ALLOWED_EMAILS


def display_name_from_user(user: Any) -> str:
    meta = getattr(user, "user_metadata", None) or {}
    if isinstance(meta, dict):
        for key in ("full_name", "name", "display_name"):
            if meta.get(key):
                return str(meta[key])
    email = getattr(user, "email", None) or ""
    return email.split("@")[0] if email else "User"


def upsert_app_user(client: Client, user: Any) -> dict[str, Any]:
    """Ensure public.users row exists for the authenticated auth.users id.

    Prefers the security-definer RPC `register_couple_user` (allow-list enforced).
    Falls back to direct upsert for older schemas.
    """
    display_name = display_name_from_user(user)
    try:
        result = client.rpc(
            "register_couple_user",
            {"p_display_name": display_name},
        ).execute()
        rows = result.data
        if isinstance(rows, list) and rows:
            return rows[0]
        if isinstance(rows, dict):
            return rows
    except Exception:
        pass

    email = (getattr(user, "email", None) or "").lower()
    payload = {
        "id": str(user.id),
        "email": email,
        "display_name": display_name,
    }
    result = client.table("users").upsert(payload, on_conflict="id").execute()
    rows = result.data or []
    return rows[0] if rows else payload
