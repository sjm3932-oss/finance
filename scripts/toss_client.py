"""Toss Securities Open API helpers (holdings + filled-order history).

Does not place orders. `GET /api/v1/trades` is market ticks, not account history;
account fills come from `GET /api/v1/orders`.

Official docs: https://developers.tossinvest.com/llms.txt
Base: https://openapi.tossinvest.com
"""

from __future__ import annotations

from typing import Any

TOSS_BASE = "https://openapi.tossinvest.com"
INSTITUTION = "토스증권"
ACCOUNT_TYPE = "brokerage"


def to_number(raw: Any) -> float:
    if raw is None or raw == "":
        return 0.0
    n = float(str(raw).replace(",", "").strip())
    if not (n == n):  # NaN
        return 0.0
    return n


def normalize_ticker(symbol: str, market_country: str | None = None) -> str:
    t = str(symbol or "").strip().upper()
    if t.endswith(".KS") or t.endswith(".KQ"):
        base = t[:-3]
        if base.isdigit() and len(base) == 6:
            return base
    if (market_country or "").upper() == "KR" and t.isdigit() and len(t) <= 6:
        return t.zfill(6)
    return t


def map_holding(item: dict[str, Any]) -> dict[str, Any] | None:
    symbol = str(item.get("symbol") or "").strip()
    if not symbol:
        return None
    qty = to_number(item.get("quantity"))
    if qty <= 0:
        return None
    currency = str(item.get("currency") or "KRW").upper()
    if currency not in {"KRW", "USD"}:
        currency = "USD" if (item.get("marketCountry") or "").upper() == "US" else "KRW"
    ticker = normalize_ticker(symbol, str(item.get("marketCountry") or ""))
    return {
        "ticker": ticker,
        "name": str(item.get("name") or ticker).strip() or ticker,
        "quantity": qty,
        "avg_price": to_number(item.get("averagePurchasePrice")),
        "currency": currency,
        "last_price": to_number(item.get("lastPrice")),
    }


def holdings_by_currency(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"KRW": [], "USD": []}
    for item in items:
        mapped = map_holding(item)
        if not mapped:
            continue
        bucket = mapped["currency"] if mapped["currency"] in out else "KRW"
        out[bucket].append(mapped)
    return out


def local_account_key(currency: str) -> tuple[str, str, str]:
    return (INSTITUTION, ACCOUNT_TYPE, currency)


def _date_prefix(raw: Any) -> str | None:
    s = str(raw or "").strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return None


def map_filled_order(order: dict[str, Any]) -> dict[str, Any] | None:
    """Map a Toss order with fills to a local trades row. Skip unfilled orders."""
    execution = order.get("execution") if isinstance(order.get("execution"), dict) else {}
    qty = to_number(execution.get("filledQuantity"))
    if qty <= 0:
        return None
    price = to_number(execution.get("averageFilledPrice"))
    if price <= 0:
        return None
    side = str(order.get("side") or "").upper()
    if side == "BUY":
        trade_type = "buy"
    elif side == "SELL":
        trade_type = "sell"
    else:
        return None
    order_id = str(order.get("orderId") or "").strip()
    if not order_id:
        return None
    symbol = str(order.get("symbol") or "").strip()
    if not symbol:
        return None
    currency = str(order.get("currency") or "KRW").upper()
    if currency not in {"KRW", "USD"}:
        currency = "USD" if not symbol.isdigit() else "KRW"
    ticker = normalize_ticker(symbol, "KR" if currency == "KRW" else "US")
    fee = to_number(execution.get("commission")) + to_number(execution.get("tax"))
    trade_date = _date_prefix(execution.get("filledAt")) or _date_prefix(
        order.get("orderedAt")
    )
    if not trade_date:
        return None
    return {
        "external_id": order_id,
        "ticker": ticker,
        "trade_type": trade_type,
        "price": price,
        "quantity": qty,
        "fee": fee,
        "currency": currency,
        "trade_date": trade_date,
        "reason": "토스 체결",
    }


def humanize_toss_error(status: int, payload: Any) -> str:
    code = ""
    message = ""
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            code = str(err.get("code") or "")
            message = str(err.get("message") or "")
        elif isinstance(err, str):
            code = err
            message = str(payload.get("error_description") or "")
    if status == 403 or code in {"edge-blocked", "forbidden"}:
        return (
            "토스 Open API가 이 IP를 막았습니다 (403). "
            "토스증권 WTS → 설정 → Open API → 허용 IP에 현재 공인 IP를 등록하세요."
        )
    if status == 401 or code in {"invalid-token", "expired-token", "invalid_client"}:
        return "토스 인증이 실패했습니다. TOSS_CLIENT_ID / TOSS_CLIENT_SECRET 을 확인하세요."
    if status == 429:
        return "토스 API 호출 한도를 넘었습니다. 잠시 후 다시 시도하세요."
    if message:
        return message
    if code:
        return f"토스 API 오류 ({code})"
    return f"토스 API HTTP {status}"
