"""Shared edge-function / job helpers."""

from __future__ import annotations

import os

import httpx

from lib.supabase_client import SUPABASE_URL, get_service_client


def invoke_edge(name: str, access_token: str = "") -> dict:
    """Call a Supabase Edge Function; prefer service role when available."""
    url = f"{SUPABASE_URL}/functions/v1/{name}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "apikey": os.getenv("SUPABASE_ANON_KEY", ""),
        "Content-Type": "application/json",
    }
    try:
        get_service_client()
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if key:
            headers["Authorization"] = f"Bearer {key}"
            headers["apikey"] = key
    except Exception:
        pass
    r = httpx.post(url, headers=headers, json={}, timeout=120.0)
    try:
        return {"status": r.status_code, "body": r.json()}
    except Exception:
        return {"status": r.status_code, "body": r.text}


def briefing_text_from_result(result: dict) -> str | None:
    """Pull briefing prose from morning-briefing function response."""
    body = result.get("body")
    if isinstance(body, dict):
        for key in ("briefing", "text", "message", "content"):
            val = body.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        # nested
        data = body.get("data")
        if isinstance(data, dict):
            for key in ("briefing", "text", "message"):
                val = data.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
        if isinstance(body.get("error"), str):
            return None
    return None
