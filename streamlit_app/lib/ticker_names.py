"""Resolve ticker/code → 종목명 for ledger display."""

from __future__ import annotations

import re
from typing import Any, Iterable

_HANGUL = re.compile(r"[\uac00-\ud7a3]")


def normalize_kr_ticker(raw: Any) -> str:
    t = str(raw or "").strip().upper()
    if not t:
        return t
    if t.endswith(".KS") or t.endswith(".KQ"):
        t = t[:-3]
    a_idx = t.find("A")
    prefix = t[:a_idx]
    if a_idx >= 0 and (not prefix or prefix.isdigit()) and t[a_idx + 1 :].isdigit():
        t = t[a_idx + 1 :]
    if t.isdigit() and len(t) <= 6:
        return t.zfill(6)
    if t.isdigit() and len(t) > 6:
        return t[-6:]
    return t


def ticker_lookup_keys(raw: Any) -> list[str]:
    orig = str(raw or "").strip()
    if not orig:
        return []
    keys: list[str] = []
    seen: set[str] = set()
    for key in (orig, orig.upper(), normalize_kr_ticker(orig)):
        if key and key not in seen:
            keys.append(key)
            seen.add(key)
    return keys


def is_ticker_like(raw: Any) -> bool:
    s = str(raw or "").strip()
    if not s:
        return True
    if _HANGUL.search(s) or " " in s:
        return False
    norm = normalize_kr_ticker(s)
    if re.fullmatch(r"\d{6}", norm):
        return True
    up = s.upper()
    if re.fullmatch(r"[0-9A-Z]{4,16}", up) and not re.search(r"[AEIOU]{2}", up):
        return any(ch.isdigit() for ch in s)
    return False


def build_name_index(rows: Iterable[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows:
        name = str(row.get("name") or "").strip()
        if not name or is_ticker_like(name):
            continue
        for key in ticker_lookup_keys(row.get("ticker")):
            existing = out.get(key)
            if existing and not is_ticker_like(existing):
                continue
            out[key] = name
    return out


def lookup_asset_name(ticker: Any, names: dict[str, str]) -> str | None:
    for key in ticker_lookup_keys(ticker):
        found = names.get(key)
        if found:
            return found
    return None


def flow_display_name(
    flow_kind: Any,
    asset_ref: Any,
    asset_name: Any = None,
    *,
    kind_ko: dict[str, str] | None = None,
) -> str:
    named = str(asset_name or "").strip()
    if named:
        return named
    ref = str(asset_ref or "").strip()
    if ref:
        return ref
    kind = str(flow_kind or "")
    return (kind_ko or {}).get(kind, kind) or "항목"


def load_name_index(client) -> dict[str, str]:
    rows: list[dict[str, Any]] = []
    if client is None:
        return {}
    try:
        rows.extend(client.table("holdings").select("ticker,name").execute().data or [])
    except Exception:
        pass
    try:
        rows.extend(
            client.table("dividends").select("ticker,name").limit(2000).execute().data
            or []
        )
    except Exception:
        pass
    return build_name_index(rows)
