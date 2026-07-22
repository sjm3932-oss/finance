"""Gemini Vision client for brokerage screenshot OCR."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

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


WEALTH_CHAT_SYSTEM = """당신은 Couples Wealth Master의 부부 공동자산 전용 비서입니다.

규칙:
1. 제공된 WEALTH_CONTEXT JSON에 있는 사실만 근거로 답하세요.
2. 컨텍스트에 없는 시세·뉴스·종목·개인정보는 추측하지 말고, "데이터에 없음"이라고 말하세요.
3. 일반적인 투자 권유·세금 확정 자문은 하지 말고, 필요하면 "참고용 추정"임을 밝히세요.
4. 한국어로 간결하고 친절하게 답하세요. 숫자에는 단위(원/달러/%)를 붙이세요.
5. 질문자가 자산과 무관한 주제(코딩, 일반상식 등)를 물으면 자산 범위 밖이라고 안내하세요.
"""


def chat_about_wealth(
    user_message: str,
    wealth_context_text: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    """Grounded chat over the couple's wealth context. history items: role=user|model."""
    if not GEMINI_API_KEY:
        raise GeminiError("GEMINI_API_KEY is not set")
    if not (user_message or "").strip():
        raise GeminiError("Empty message")

    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise GeminiError("google-generativeai is not installed") from exc

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        GEMINI_MODEL,
        system_instruction=WEALTH_CHAT_SYSTEM,
    )

    contents: list[Any] = [
        {
            "role": "user",
            "parts": [
                "WEALTH_CONTEXT (유일한 사실 소스):\n"
                + wealth_context_text
                + "\n\n위 컨텍스트만 사용해 이후 질문에 답하세요. 이해했으면 '준비됨'이라고만 답하세요."
            ],
        },
        {"role": "model", "parts": ["준비됨"]},
    ]

    for turn in history or []:
        role = turn.get("role")
        text = (turn.get("content") or "").strip()
        if not text or role not in ("user", "model"):
            continue
        contents.append({"role": role, "parts": [text]})

    contents.append({"role": "user", "parts": [user_message.strip()]})

    response = model.generate_content(
        contents,
        generation_config={"temperature": 0.3},
    )
    text = getattr(response, "text", None)
    if not text:
        raise GeminiError("Empty response from Gemini chat")
    return text.strip()
