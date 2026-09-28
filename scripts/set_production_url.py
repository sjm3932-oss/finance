#!/usr/bin/env python3
"""Point Supabase Auth + app_runtime at the fixed Vercel production URL.

Usage:
  .venv/bin/python scripts/set_production_url.py https://richddoong.vercel.app
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

PROJECT_REF = "lsqkixysysfhywipmrky"


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].startswith("http"):
        print("Usage: set_production_url.py https://richddoong.vercel.app")
        return 2
    url = sys.argv[1].rstrip("/")
    env_path = Path(__file__).resolve().parents[1] / ".env"
    vals = dotenv_values(env_path) if env_path.exists() else {}
    token = vals.get("SUPABASE_ACCESS_TOKEN") or os.environ.get("SUPABASE_ACCESS_TOKEN")
    supabase_url = (
        vals.get("SUPABASE_URL")
        or os.environ.get("SUPABASE_URL")
        or f"https://{PROJECT_REF}.supabase.co"
    )
    service_key = vals.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get(
        "SUPABASE_SERVICE_ROLE_KEY"
    )
    if not token:
        print("SUPABASE_ACCESS_TOKEN missing")
        return 1

    allow = ",".join(
        [
            "http://localhost:3000",
            "http://localhost:3000/**",
            url,
            url + "/**",
            url + "/auth/callback",
        ]
    )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = httpx.patch(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/config/auth",
        headers=headers,
        json={"site_url": url, "uri_allow_list": allow},
        timeout=60,
    )
    print("PATCH auth", r.status_code)
    d = httpx.get(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/config/auth",
        headers=headers,
        timeout=60,
    ).json()
    print("site_url =", d.get("site_url"))
    print("uri_allow_list =", d.get("uri_allow_list"))

    if service_key:
        rt = httpx.patch(
            f"{supabase_url.rstrip('/')}/rest/v1/app_runtime?id=eq.1",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json={"public_url": url, "fallback_url": None},
            timeout=60,
        )
        print("PATCH app_runtime", rt.status_code, rt.text)
    else:
        print("SUPABASE_SERVICE_ROLE_KEY missing — skipped app_runtime update")

    if env_path.exists():
        lines = []
        found = False
        for line in env_path.read_text().splitlines():
            if line.startswith("PUBLIC_APP_URL="):
                lines.append(f"PUBLIC_APP_URL={url}")
                found = True
            elif line.startswith("STABLE_APP_URL="):
                lines.append(f"STABLE_APP_URL={url}")
            else:
                lines.append(line)
        if not found:
            lines.append(f"PUBLIC_APP_URL={url}")
        env_path.write_text("\n".join(lines) + "\n")
        print("Updated .env PUBLIC_APP_URL")

    print()
    print("Next:")
    print("  1) Vercel env PUBLIC_APP_URL / production alias가 같은 호스트인지 확인")
    print("  2) Google Cloud OAuth 리다이렉트에 Supabase 콜백만 있으면 됩니다:")
    print(f"     https://{PROJECT_REF}.supabase.co/auth/v1/callback")
    print("  3) Edge: supabase functions deploy app-gateway --project-ref", PROJECT_REF)
    return 0 if r.status_code < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
