#!/usr/bin/env python3
"""Point Supabase Auth Site URL at the Next.js production host.

Usage:
  python3 scripts/set_production_url.py https://richddoong.vercel.app

Google login on the Next app must return to Vercel, not Streamlit.
Site URL is the fallback when redirectTo is missing or not allow-listed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

PROJECT_REF = "lsqkixysysfhywipmrky"
DEFAULT_NEXT = "https://richddoong.vercel.app"
STREAMLIT = "https://richddoong.streamlit.app"


def allow_list(site: str) -> str:
    urls = [
        site,
        f"{site}/**",
        f"{site}/auth/callback",
        "https://richddoong.vercel.app",
        "https://richddoong.vercel.app/**",
        "https://richddoong.vercel.app/auth/callback",
        "https://richddoong-*-920723.vercel.app/**",
        "http://localhost:3000",
        "http://localhost:3000/**",
        "http://localhost:3000/auth/callback",
        STREAMLIT,
        f"{STREAMLIT}/**",
        "http://localhost:8501",
        "http://localhost:8501/**",
    ]
    seen: list[str] = []
    for u in urls:
        if u not in seen:
            seen.append(u)
    return ",".join(seen)


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].startswith("http"):
        print(f"Usage: set_production_url.py {DEFAULT_NEXT}")
        return 2
    url = sys.argv[1].rstrip("/")
    env_path = Path(__file__).resolve().parents[1] / ".env"
    vals = dotenv_values(env_path) if env_path.exists() else {}
    token = vals.get("SUPABASE_ACCESS_TOKEN") or os.environ.get("SUPABASE_ACCESS_TOKEN")
    if not token:
        print("SUPABASE_ACCESS_TOKEN missing")
        return 1

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = httpx.patch(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/config/auth",
        headers=headers,
        json={"site_url": url, "uri_allow_list": allow_list(url)},
        timeout=60,
    )
    print("PATCH", r.status_code)
    if r.status_code >= 400:
        print(r.text[:1500])
    d = httpx.get(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/config/auth",
        headers=headers,
        timeout=60,
    ).json()
    print("site_url =", d.get("site_url"))
    print("uri_allow_list =", d.get("uri_allow_list"))

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
    print("  1) Bookmark https://richddoong.vercel.app (not Streamlit)")
    print("  2) Google Cloud OAuth redirect stays the Supabase callback:")
    print(f"     https://{PROJECT_REF}.supabase.co/auth/v1/callback")
    return 0 if r.status_code < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
