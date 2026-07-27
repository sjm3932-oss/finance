"""Server-side auth token store keyed by a short browser session id.

JWT access/refresh tokens are too large/fragile for cookie-only persistence
(especially with Streamlit CookieManager + immediate reruns). We keep only a
small `cwm_sid` cookie in the browser and store tokens on disk.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

STORE_DIR = Path(__file__).resolve().parents[1] / ".data" / "sessions"
SESSION_TTL_SEC = 60 * 24 * 3600  # 60 days


def new_sid() -> str:
    return uuid.uuid4().hex


def _path(sid: str) -> Path:
    safe = "".join(c for c in sid if c.isalnum())
    return STORE_DIR / f"{safe}.json"


def save_tokens(sid: str, access_token: str, refresh_token: str | None) -> None:
    if not sid or not access_token:
        return
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "updated_at": time.time(),
    }
    path = _path(sid)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)


def load_tokens(sid: str) -> dict[str, Any] | None:
    if not sid:
        return None
    path = _path(sid)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    updated = float(data.get("updated_at") or 0)
    if updated and (time.time() - updated) > SESSION_TTL_SEC:
        delete_tokens(sid)
        return None
    if not data.get("access_token"):
        return None
    return data


def delete_tokens(sid: str) -> None:
    if not sid:
        return
    path = _path(sid)
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def touch(sid: str) -> None:
    data = load_tokens(sid)
    if not data:
        return
    save_tokens(sid, data["access_token"], data.get("refresh_token"))
