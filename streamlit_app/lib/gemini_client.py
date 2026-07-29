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
- Tickers: US/ETF as Latin symbols (TQQQ, TSLA). Korean listed stocks as 6-digit codes (e.g. 005930) without .KS/.KQ.
- CRITICAL — ticker AND name are BOTH required on every trade, dividend, and holdings_snapshot row:
  * Never leave "name" empty if you have a ticker.
  * Never leave "ticker" empty if you have a Korean/English stock name.
  * Korean broker screens often show only the company name (삼성전자, SK하이닉스) — you MUST still output the 6-digit ticker (005930, 000660) when known.
  * Screens that show only a 6-digit code — you MUST still output the Korean company full name.
  * "name" must be the human-readable full name (삼성전자), never the same as the ticker code.
  * Examples: {"ticker":"005930","name":"삼성전자"}, {"ticker":"QQQM","name":"Invesco NASDAQ 100 ETF"}.
- If nothing can be parsed, return {"trades":[],"dividends":[],"holdings_snapshot":[],"debts":[],"debt_payments":[],"error":"unreadable"}.
"""

DOC_TYPE_HINTS = {
    "holdings": (
        "This screenshot is mainly a holdings/balance screen. Focus on holdings_snapshot. "
        "Every row MUST include both ticker and full Korean/English name."
    ),
    "trades": (
        "This screenshot is mainly a trade/order history. Focus on trades (buy/sell). "
        "Every trade MUST include both ticker and full name."
    ),
    "dividends": (
        "This screenshot is mainly dividend / 배당 payout history. Focus on dividends. "
        "Every dividend MUST include both ticker and full name."
    ),
    "debt": (
        "This screenshot is a loan/debt statement: 대출 잔금, 이자율, 월 납부/원리금 내역. "
        "Focus on debts and debt_payments."
    ),
    "auto": (
        "Detect whether this is holdings, trades, dividends, debt/loan, or a mix, "
        "and fill matching arrays. Equity rows MUST always include both ticker and name."
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


WEALTH_CHAT_SYSTEM = """당신은 부자뚱의 생활밀착형 자산 선생님입니다.
정명·지수가 일상에서 묻는 돈 고민(투자·연금·세금·대출·현금·환율·시세)을
일반인도 바로 이해하게, 쉽고 짧게 설명해 주세요.

말투: 존댓말, 따뜻하고 차분. 이모지 금지.  thr 핵심만.
할루시네이션 금지: WEALTH_CONTEXT 숫자만 사실. 원인·제도는 확인된 범위만. 매수·매도 권유·세금 확정 단정 금지.
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
