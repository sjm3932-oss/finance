"""Gemini Vision client for brokerage screenshot OCR."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

OCR_PROMPT = """You are a financial OCR assistant for a Korean couple's portfolio tracker.
Extract holdings and/or trades from this brokerage/bank screenshot.

Return ONLY valid JSON (no markdown) with this schema:
{
  "account_hint": "institution name if visible",
  "trades": [
    {
      "trade_date": "YYYY-MM-DD",
      "ticker": "string",
      "name": "string",
      "trade_type": "buy" | "sell",
      "price": number,
      "quantity": number,
      "reason": "string or empty"
    }
  ],
  "holdings_snapshot": [
    {
      "ticker": "string",
      "name": "string",
      "quantity": number,
      "avg_price": number,
      "currency": "KRW" | "USD"
    }
  ]
}

Rules:
- Prefer holdings_snapshot when the screen shows balances/positions.
- Prefer trades when the screen shows buy/sell history.
- Use empty arrays when a section is not visible.
- Numbers must be plain JSON numbers (no commas).
- If nothing can be parsed, return {"trades":[],"holdings_snapshot":[],"error":"unreadable"}.
"""


class GeminiError(RuntimeError):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise GeminiError("Gemini response did not contain JSON")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise GeminiError("Gemini JSON root must be an object")
    return data


def parse_screenshot(image_bytes: bytes, mime_type: str = "image/png") -> dict[str, Any]:
    if not GEMINI_API_KEY:
        raise GeminiError("GEMINI_API_KEY is not set")

    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise GeminiError("google-generativeai is not installed") from exc

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    response = model.generate_content(
        [
            OCR_PROMPT,
            {"mime_type": mime_type, "data": image_bytes},
        ],
        generation_config={"temperature": 0.1},
    )

    text = getattr(response, "text", None)
    if not text:
        raise GeminiError("Empty response from Gemini Vision")

    parsed = _extract_json(text)
    parsed.setdefault("trades", [])
    parsed.setdefault("holdings_snapshot", [])
    if not isinstance(parsed["trades"], list):
        parsed["trades"] = []
    if not isinstance(parsed["holdings_snapshot"], list):
        parsed["holdings_snapshot"] = []
    return parsed
