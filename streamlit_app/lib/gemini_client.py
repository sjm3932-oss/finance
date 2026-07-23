"""Gemini Vision client for brokerage screenshot OCR."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from lib.env_boot import env, hydrate_env

hydrate_env()

GEMINI_API_KEY = env("GEMINI_API_KEY")
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-2.5-flash")

OCR_PROMPT = """You are a financial OCR assistant for a Korean couple's wealth tracker (부자뚱).
Extract holdings, trades, dividends, and/or debt (loan) info from this screenshot.

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
      "fee": number,
      "currency": "KRW" | "USD",
      "reason": "string or empty"
    }
  ],
  "dividends": [
    {
      "pay_date": "YYYY-MM-DD",
      "ticker": "string",
      "name": "string",
      "amount": number,
      "currency": "KRW" | "USD",
      "memo": "string or empty"
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
  ],
  "debts": [
    {
      "lender": "은행/대출상품명",
      "debt_kind": "mortgage" | "credit" | "card" | "student" | "jeonse" | "other",
      "balance": number,
      "original_principal": number_or_null,
      "interest_rate": number_or_null,
      "due_date": "YYYY-MM-DD or null",
      "memo": "string or empty"
    }
  ],
  "debt_payments": [
    {
      "pay_date": "YYYY-MM-DD",
      "lender": "은행/대출상품명 (match debts)",
      "amount": number,
      "interest_portion": number_or_null,
      "principal_portion": number_or_null,
      "balance_after": number_or_null,
      "rate": number_or_null,
      "memo": "string or empty"
    }
  ]
}

Rules:
- Prefer holdings_snapshot when the screen shows balances/positions.
- Prefer trades when the screen shows buy/sell / order history.
- Prefer dividends when the screen shows dividend / 배당 / 입금 내역 for dividends.
- Prefer debts when the screen shows loan balance / 대출잔액 / 원리금 / 이자율 / 상환스케줄 summary.
- Prefer debt_payments when the screen shows monthly payment history / 납부내역 / 이자·원금 분해.
- debt.balance = 잔금 (remaining balance), NOT the original loan amount unless they are the same.
- debt_kind: 주택담보/주담대→mortgage, 신용→credit, 카드론→card, 학자금→student, 전세→jeonse, else other.
- For debt_payments: amount is total paid (원리금 합계). If interest/principal split is visible, fill both; otherwise leave null.
- Fill every section that is visible; use empty arrays when not visible.
- Numbers must be plain JSON numbers (no commas, no currency symbols). Won amounts as integers when possible.
- Tickers stay as Latin symbols (e.g. TQQQ, TSLA). Korean names go in "name".
- If nothing can be parsed, return {"trades":[],"dividends":[],"holdings_snapshot":[],"debts":[],"debt_payments":[],"error":"unreadable"}.
"""

DOC_TYPE_HINTS = {
    "holdings": "This screenshot is mainly a holdings/balance screen. Focus on holdings_snapshot.",
    "trades": "This screenshot is mainly a trade/order history. Focus on trades (buy/sell).",
    "dividends": "This screenshot is mainly dividend / 배당 payout history. Focus on dividends.",
    "debt": (
        "This screenshot is a loan/debt statement: 대출 잔금, 이자율, 월 납부/원리금 내역. "
        "Focus on debts and debt_payments."
    ),
    "auto": (
        "Detect whether this is holdings, trades, dividends, debt/loan, or a mix, "
        "and fill matching arrays."
    ),
}


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


def parse_screenshot(
    image_bytes: bytes,
    mime_type: str = "image/png",
    doc_type: str = "auto",
) -> dict[str, Any]:
    if not GEMINI_API_KEY:
        raise GeminiError("GEMINI_API_KEY is not set")

    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise GeminiError("google-generativeai is not installed") from exc

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    hint = DOC_TYPE_HINTS.get(doc_type, DOC_TYPE_HINTS["auto"])
    prompt = OCR_PROMPT + f"\n\nDocument hint: {hint}\n"

    response = model.generate_content(
        [
            prompt,
            {"mime_type": mime_type, "data": image_bytes},
        ],
        generation_config={"temperature": 0.1},
    )

    text = getattr(response, "text", None)
    if not text:
        raise GeminiError("Empty response from Gemini Vision")

    parsed = _extract_json(text)
    for key in ("trades", "dividends", "holdings_snapshot", "debts", "debt_payments"):
        parsed.setdefault(key, [])
        if not isinstance(parsed[key], list):
            parsed[key] = []
    return parsed


WEALTH_CHAT_SYSTEM = """당신은 부자뚱의 부부 공동자산 전용 비서입니다.

규칙:
1. 제공된 WEALTH_CONTEXT JSON의 포트폴리오/시세/스냅샷/세금 수치를 사실의 1순위 근거로 쓰세요.
2. WEALTH_CONTEXT.recent_chat_logs 와 이어지는 대화 history는 맥락·의도 파악용입니다.
   - 예: "아까 말한 그 종목" → 이전 로그에서 무엇을 가리켰는지 해석하세요.
   - 과거 로그의 숫자와 현재 holdings/prices가 다르면 **현재 수치를 우선**하고, 달라졌다고 짧게 알려주세요.
3. 컨텍스트에 없는 시세·뉴스·종목·개인정보는 추측하지 말고, "데이터에 없음"이라고 말하세요.
4. 일반적인 투자 권유·세금 확정 자문은 하지 말고, 필요하면 "참고용 추정"임을 밝히세요.
5. 한국어로 간결하고 친절하게 답하세요. 숫자에는 단위(원/달러/%)를 붙이세요.
6. 질문자가 자산과 무관한 주제(코딩, 일반상식 등)를 물으면 자산 범위 밖이라고 안내하세요.
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
                "WEALTH_CONTEXT (포트폴리오 사실 + recent_chat_logs):\n"
                + wealth_context_text
                + "\n\n숫자 사실은 holdings/prices/snapshots를 우선하고, "
                "recent_chat_logs와 이후 history로 대화 맥락을 이어가세요. "
                "이해했으면 '준비됨'이라고만 답하세요."
            ],
        },
        {"role": "model", "parts": ["준비됨"]},
    ]

    # Cap history to last N turns to control token use
    trimmed = list(history or [])[-40:]
    for turn in trimmed:
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
