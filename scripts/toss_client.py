"""Toss Securities Open API helpers (holdings + filled-order history).

Does not place orders. `GET /api/v1/trades` is market ticks, not account history;
account fills come from `GET /api/v1/orders`.

Official docs: https://developers.tossinvest.com/llms.txt
Base: https://openapi.tossinvest.com
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

TOSS_BASE = "https://openapi.tossinvest.com"
INSTITUTION = "토스증권"
ACCOUNT_TYPE = "brokerage"
KST = ZoneInfo("Asia/Seoul")


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


def _dict_list(val: Any) -> list[dict[str, Any]] | None:
    if isinstance(val, list):
        return [row for row in val if isinstance(row, dict)]
    return None


def extract_orders(payload: Any) -> list[dict[str, Any]]:
    """Unwrap Toss getOrders payloads (`result.orders`, nested data, or a bare list)."""
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    result = payload.get("result")
    listed = _dict_list(result)
    if listed is not None:
        return listed
    blobs: list[Any] = []
    if isinstance(result, dict):
        blobs.append(result)
        nested = result.get("data")
        if isinstance(nested, dict):
            blobs.append(nested)
        listed = _dict_list(nested)
        if listed is not None:
            return listed
    blobs.append(payload)
    for blob in blobs:
        if not isinstance(blob, dict):
            continue
        for key in ("orders", "items", "list"):
            listed = _dict_list(blob.get(key))
            if listed is not None:
                return listed
    return []


def extract_holdings_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    result = payload.get("result")
    listed = _dict_list(result)
    if listed is not None:
        return listed
    blob = result if isinstance(result, dict) else payload
    if not isinstance(blob, dict):
        return []
    for key in ("items", "holdings", "list"):
        listed = _dict_list(blob.get(key))
        if listed is not None:
            return listed
    return []


def pagination_cursor(payload: Any) -> tuple[bool, str | None]:
    blob: Any = payload
    if isinstance(payload, dict) and isinstance(payload.get("result"), dict):
        blob = payload["result"]
    if not isinstance(blob, dict):
        return False, None
    cursor = blob.get("nextCursor") or blob.get("next_cursor") or blob.get("next")
    has_next = bool(blob.get("hasNext") if "hasNext" in blob else blob.get("has_next"))
    if not has_next and cursor:
        has_next = True
    return has_next, str(cursor) if cursor else None


def _execution_blob(order: dict[str, Any]) -> dict[str, Any]:
    """Prefer nested execution, but some payloads flatten fill fields onto the order."""
    nested = order.get("execution") if isinstance(order.get("execution"), dict) else {}
    out = dict(nested)
    for key in (
        "filledQuantity",
        "averageFilledPrice",
        "filledAmount",
        "commission",
        "tax",
        "filledAt",
        "settlementDate",
    ):
        if out.get(key) in (None, "") and order.get(key) not in (None, ""):
            out[key] = order[key]
    return out


def _trade_side(raw: Any) -> str | None:
    side = str(raw or "").strip().upper()
    if side in {"BUY", "B", "매수"} or "매수" in str(raw or ""):
        return "buy"
    if side in {"SELL", "S", "매도"} or "매도" in str(raw or ""):
        return "sell"
    return None


def map_filled_order(order: dict[str, Any]) -> dict[str, Any] | None:
    """Map a Toss order with fills to a local trades row. Skip unfilled orders."""
    if not isinstance(order, dict):
        return None
    execution = _execution_blob(order)
    qty = to_number(execution.get("filledQuantity"))
    if qty <= 0:
        return None
    price = to_number(execution.get("averageFilledPrice"))
    if price <= 0:
        filled_amt = to_number(execution.get("filledAmount"))
        if filled_amt > 0:
            price = filled_amt / qty
    if price <= 0:
        price = to_number(order.get("price"))
    if price <= 0:
        return None
    trade_type = _trade_side(order.get("side"))
    if not trade_type:
        return None
    order_id = str(order.get("orderId") or order.get("id") or "").strip()
    if not order_id:
        return None
    stock = order.get("stock") if isinstance(order.get("stock"), dict) else {}
    symbol = str(
        order.get("symbol")
        or order.get("ticker")
        or stock.get("symbol")
        or stock.get("stockCode")
        or ""
    ).strip()
    if not symbol:
        return None
    currency = str(order.get("currency") or "KRW").upper()
    if currency not in {"KRW", "USD"}:
        currency = "USD" if not symbol.isdigit() else "KRW"
    ticker = normalize_ticker(symbol, "KR" if currency == "KRW" else "US")
    fee = to_number(execution.get("commission")) + to_number(execution.get("tax"))
    trade_date = (
        _date_prefix(execution.get("filledAt"))
        or _date_prefix(execution.get("settlementDate"))
        or _date_prefix(order.get("orderedAt"))
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


def date_windows(start: str, end: str, days: int) -> list[tuple[str, str]]:
    """Inclusive YYYY-MM-DD windows of at most `days` length."""
    step = max(1, days)
    try:
        cur = datetime.fromisoformat(start).date()
        last = datetime.fromisoformat(end).date()
    except ValueError:
        return [(start, end)]
    if cur > last:
        return []
    out: list[tuple[str, str]] = []
    while cur <= last:
        nxt = min(cur + timedelta(days=step - 1), last)
        out.append((cur.isoformat(), nxt.isoformat()))
        cur = nxt + timedelta(days=1)
    return out


def parse_yahoo_dividends(
    payload: Any,
    *,
    ticker: str,
    quantity: float,
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    """Map Yahoo chart events.dividends into Toss dividend rows (qty × DPS)."""
    if quantity <= 0:
        return []
    result = ((payload or {}).get("chart") or {}).get("result") or []
    if not result:
        return []
    events = (result[0].get("events") or {}).get("dividends") or {}
    items = events.values() if isinstance(events, dict) else events
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        dps = to_number(item.get("amount"))
        ts = item.get("date")
        if dps <= 0 or ts in (None, ""):
            continue
        try:
            pay_date = datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
        except (TypeError, ValueError, OSError):
            continue
        if pay_date < start or pay_date > end:
            continue
        amount = round(dps * quantity, 6)
        if amount <= 0:
            continue
        out.append(
            {
                "external_id": f"toss:div:{ticker}:{pay_date}:{dps:.6f}",
                "ticker": ticker,
                "pay_date": pay_date,
                "amount": amount,
                "currency": "USD" if not str(ticker).isdigit() else "KRW",
                "memo": "토스 배당(추정)",
            }
        )
    return out


def yahoo_chart_symbol(ticker: str) -> list[str]:
    t = normalize_ticker(ticker)
    if t.isdigit() and len(t) == 6:
        return [f"{t}.KS", f"{t}.KQ"]
    return [t]


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
    if code == "closed-not-supported":
        return (
            "토스 Open API가 종료 주문 목록(CLOSED)을 이 계정에서 아직 지원하지 않습니다. "
            "진행 중 주문(OPEN)과 보유 종목 기준 배당은 그대로 가져옵니다."
        )
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


def parse_auto_sync_hours(raw: str | None) -> list[int]:
    if raw is None or not str(raw).strip():
        raw = "6,16"
    hours: list[int] = []
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            hour = int(part)
        except ValueError:
            continue
        if 0 <= hour <= 23:
            hours.append(hour)
    return sorted(set(hours)) or [6, 16]


def kst_auto_sync_due(
    now: datetime,
    last_ok: datetime | None,
    hours: list[int],
) -> bool:
    """True when a KST clock slot (e.g. 06:00, 16:00) is due and not yet synced."""
    if not hours:
        return False
    now_kst = now.replace(tzinfo=KST) if now.tzinfo is None else now.astimezone(KST)
    last = None
    if last_ok is not None:
        last = (
            last_ok.replace(tzinfo=KST)
            if last_ok.tzinfo is None
            else last_ok.astimezone(KST)
        )
    for hour in hours:
        deadline = now_kst.replace(hour=hour, minute=0, second=0, microsecond=0)
        if now_kst < deadline:
            continue
        if last is not None and last >= deadline:
            continue
        return True
    return False
