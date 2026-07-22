"""Shared OCR → staging helpers (잔고 / 매매 / 배당)."""

from __future__ import annotations

import mimetypes
import uuid
from datetime import datetime, timezone
from typing import Any

from lib.gemini_client import GeminiError, parse_screenshot

DOC_TYPES = {
    "auto": "자동 인식 (잔고·매매·배당)",
    "holdings": "잔고/보유",
    "trades": "매매 내역",
    "dividends": "배당 내역",
}


def stage_screenshot(
    client,
    *,
    user_id: str,
    account_id: str,
    image_bytes: bytes,
    filename: str,
    mime_type: str | None = None,
    doc_type: str = "auto",
) -> tuple[dict[str, Any] | None, str, dict[str, Any], str | None]:
    """Upload image, run Gemini OCR, insert ocr_staging.

    Returns (created_row, status, parsed_json, error_msg).
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

    parsed_json: dict[str, Any] = {
        "account_id": account_id,
        "doc_type": doc_type,
        "trades": [],
        "dividends": [],
        "holdings_snapshot": [],
    }
    status = "pending"
    error_msg: str | None = None

    try:
        parsed = parse_screenshot(image_bytes, mime_type=mime, doc_type=doc_type)
        parsed["account_id"] = account_id
        parsed["doc_type"] = doc_type
        parsed.setdefault("trades", [])
        parsed.setdefault("dividends", [])
        parsed.setdefault("holdings_snapshot", [])
        parsed_json = parsed
        empty = (
            not parsed.get("trades")
            and not parsed.get("dividends")
            and not parsed.get("holdings_snapshot")
        )
        if parsed.get("error") == "unreadable" and empty:
            status = "failed"
            error_msg = "스크린샷을 읽을 수 없습니다"
        elif empty:
            status = "failed"
            error_msg = "추출된 매매·배당·잔고가 없습니다"
    except GeminiError as exc:
        status = "failed"
        error_msg = str(exc)
        parsed_json = {
            "account_id": account_id,
            "doc_type": doc_type,
            "trades": [],
            "dividends": [],
            "holdings_snapshot": [],
            "error": str(exc),
        }

    row = {
        "uploaded_by": str(user_id),
        "image_url": object_path,
        "parsed_json": parsed_json,
        "status": status,
    }
    insert = client.table("ocr_staging").insert(row).execute()
    created = (insert.data or [None])[0]
    return created, status, parsed_json, error_msg
