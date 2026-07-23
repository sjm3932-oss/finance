"""Shared OCR → staging helpers (잔고 / 매매 / 배당 / 부채)."""

from __future__ import annotations

import mimetypes
import uuid
from datetime import datetime, timezone
from typing import Any

from lib.gemini_client import GeminiError, parse_screenshot

DOC_TYPES = {
    "auto": "자동 인식 (잔고·매매·배당·부채)",
    "holdings": "잔고/보유",
    "trades": "매매 내역",
    "dividends": "배당 내역",
    "debt": "부채 명세/납부",
}

_EMPTY_KEYS = ("trades", "dividends", "holdings_snapshot", "debts", "debt_payments")


def _empty_payload(account_id: str | None, doc_type: str, **extra: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "account_id": account_id,
        "doc_type": doc_type,
        "trades": [],
        "dividends": [],
        "holdings_snapshot": [],
        "debts": [],
        "debt_payments": [],
    }
    data.update(extra)
    return data


def _is_empty(parsed: dict[str, Any]) -> bool:
    return all(not parsed.get(k) for k in _EMPTY_KEYS)


def stage_screenshot(
    client,
    *,
    user_id: str,
    account_id: str | None,
    image_bytes: bytes,
    filename: str,
    mime_type: str | None = None,
    doc_type: str = "auto",
) -> tuple[dict[str, Any] | None, str, dict[str, Any], str | None]:
    """Upload image, run Gemini OCR, insert ocr_staging.

    Returns (created_row, status, parsed_json, error_msg).
    account_id may be None for debt-only uploads (still recommended when linking a loan account).
    """
    mime = mime_type or mimetypes.guess_type(filename)[0] or "image/png"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = filename.replace("/", "_")
    object_path = f"{user_id}/{stamp}_{uuid.uuid4().hex}_{safe_name}"

    storage = client.storage.from_("ocr-screenshots")
    storage.upload(
        object_path,
        image_bytes,
        file_options={"content-type": mime, "upsert": "false"},
    )

    parsed_json: dict[str, Any] = _empty_payload(account_id, doc_type)
    status = "pending"
    error_msg: str | None = None

    try:
        parsed = parse_screenshot(image_bytes, mime_type=mime, doc_type=doc_type)
        parsed["account_id"] = account_id
        parsed["doc_type"] = doc_type
        for key in _EMPTY_KEYS:
            parsed.setdefault(key, [])
            if not isinstance(parsed[key], list):
                parsed[key] = []
        parsed_json = parsed
        empty = _is_empty(parsed)
        if parsed.get("error") == "unreadable" and empty:
            status = "failed"
            error_msg = "스크린샷을 읽을 수 없습니다"
        elif empty:
            status = "failed"
            error_msg = "추출된 매매·배당·잔고·부채가 없습니다"
    except GeminiError as exc:
        status = "failed"
        error_msg = str(exc)
        parsed_json = _empty_payload(account_id, doc_type, error=str(exc))

    row = {
        "uploaded_by": str(user_id),
        "image_url": object_path,
        "parsed_json": parsed_json,
        "status": status,
    }
    insert = client.table("ocr_staging").insert(row).execute()
    created = (insert.data or [None])[0]
    return created, status, parsed_json, error_msg
