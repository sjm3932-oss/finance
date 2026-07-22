"""Tests for server-side session token store."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "streamlit_app"
sys.path.insert(0, str(ROOT))

from lib import session_store  # noqa: E402


def test_save_load_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(session_store, "STORE_DIR", tmp_path)
    sid = session_store.new_sid()
    session_store.save_tokens(sid, "access-1", "refresh-1")
    data = session_store.load_tokens(sid)
    assert data is not None
    assert data["access_token"] == "access-1"
    assert data["refresh_token"] == "refresh-1"
    session_store.delete_tokens(sid)
    assert session_store.load_tokens(sid) is None


def test_ttl_expiry(tmp_path, monkeypatch):
    monkeypatch.setattr(session_store, "STORE_DIR", tmp_path)
    monkeypatch.setattr(session_store, "SESSION_TTL_SEC", 1)
    sid = session_store.new_sid()
    session_store.save_tokens(sid, "a", "b")
    path = session_store._path(sid)
    raw = path.read_text(encoding="utf-8")
    import json

    payload = json.loads(raw)
    payload["updated_at"] = time.time() - 10
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert session_store.load_tokens(sid) is None
