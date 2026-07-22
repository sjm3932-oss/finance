#!/usr/bin/env python3
"""Point Supabase Auth Site URL at a fixed production Streamlit URL.

Usage:
  .venv/bin/python scripts/set_production_url.py https://YOUR-APP.streamlit.app
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].startswith("http"):
        print("Usage: set_production_url.py https://your-app.streamlit.app")
        return 2
    url = sys.argv[1].rstrip("/")
    env_path = Path(__file__).resolve().parents[1] / ".env"
    vals = dotenv_values(env_path)
    token = vals.get("SUPABASE_ACCESS_TOKEN") or os.environ.get("SUPABASE_ACCESS_TOKEN")
    if not token:
        print("SUPABASE_ACCESS_TOKEN missing")
        return 1

    allow = ",".join(
        [
            "http://localhost:8501",
            "http://localhost:8501/**",
            url,
            url + "/**",
        ]
    )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = httpx.patch(
        "https://api.supabase.com/v1/projects/lsqkixysysfhywipmrky/config/auth",
        headers=headers,
        json={"site_url": url, "uri_allow_list": allow},
        timeout=60,
    )
    print("PATCH", r.status_code)
    d = httpx.get(
        "https://api.supabase.com/v1/projects/lsqkixysysfhywipmrky/config/auth",
        headers=headers,
        timeout=60,
    ).json()
    print("site_url =", d.get("site_url"))
    print("uri_allow_list =", d.get("uri_allow_list"))

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
    print("  1) Streamlit Cloud Secrets에도 PUBLIC_APP_URL을 같은 값으로 넣으세요")
    print("  2) Google Cloud OAuth 리다이렉트에 Supabase 콜백이 있는지 확인:")
    print("     https://lsqkixysysfhywipmrky.supabase.co/auth/v1/callback")
    return 0 if r.status_code < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
