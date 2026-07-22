"""Supabase client helpers for Couples Wealth Master."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from lib.env_boot import app_base_url, env, hydrate_env

hydrate_env()

SUPABASE_URL = env("SUPABASE_URL", "https://lsqkixysysfhywipmrky.supabase.co").rstrip("/")
SUPABASE_ANON_KEY = env("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = env("SUPABASE_SERVICE_ROLE_KEY")
ALLOWED_EMAILS = {
    e.strip().lower()
    for e in env("ALLOWED_EMAILS").split(",")
    if e.strip()
}


def get_public_app_url() -> str:
    """Canonical public origin (production Streamlit URL or localhost)."""
    return app_base_url()


def get_stable_app_url() -> str:
    """OAuth redirect URL — same as public app URL in proper deployments."""
    return app_base_url()


# Back-compat for importers
PUBLIC_APP_URL = get_public_app_url()
STABLE_APP_URL = get_stable_app_url()


class ConfigError(RuntimeError):
    pass


def require_env() -> None:
    hydrate_env()
    global SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, ALLOWED_EMAILS
    SUPABASE_URL = env("SUPABASE_URL", "https://lsqkixysysfhywipmrky.supabase.co").rstrip("/")
    SUPABASE_ANON_KEY = env("SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY = env("SUPABASE_SERVICE_ROLE_KEY")
    ALLOWED_EMAILS = {
        e.strip().lower()
        for e in env("ALLOWED_EMAILS").split(",")
        if e.strip()
    }
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_ANON_KEY:
        missing.append("SUPABASE_ANON_KEY")
    if missing:
        raise ConfigError(
            "Missing required env vars: " + ", ".join(missing)
            + ". Set Streamlit Cloud Secrets or copy .env.example to .env."
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
    """Ensure public.users row exists for the authenticated auth.users id."""
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
