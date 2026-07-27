"""Market price + FX helpers (Naver KR / Yahoo US / Frankfurter FX)."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx

# Tickers that are not on public markets
PRIVATE_OR_UNLISTED = {"SPACEX", "PRIVATE"}

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
NAVER_BASIC = "https://m.stock.naver.com/api/stock/{code}/basic"
FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"
STALE_HOURS = float(os.getenv("MARKET_PRICE_STALE_HOURS", "24"))

_UA = {"User-Agent": "Mozilla/5.0 (compatible; Bujattung/1.0)"}
_KR_CODE = re.compile(r"^\d{6}$")


class MarketDataError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_ticker(raw: str | None) -> str:
    t = str(raw or "").strip().upper()
    if t.endswith(".KS") or t.endswith(".KQ"):
        base = t[:-3]
        if _KR_CODE.match(base):
            return base
    return t


def is_korean_ticker(ticker: str | None) -> bool:
    """Domestic KRX codes are 6-digit (optionally stored with .KS/.KQ)."""
    return bool(_KR_CODE.match(normalize_ticker(ticker)))


def _parse_kr_number(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip().replace(",", "").replace(" ", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_naver_price(ticker: str, timeout: float = 15.0) -> dict[str, Any]:
    """KR stock/ETF quote from Naver mobile stock API. Stores 6-digit ticker."""
    code = normalize_ticker(ticker)
    if not _KR_CODE.match(code):
        raise MarketDataError(f"Not a Korean ticker: {ticker}")

    with httpx.Client(timeout=timeout, headers=_UA, follow_redirects=True) as client:
        resp = client.get(NAVER_BASIC.format(code=code))
        resp.raise_for_status()
        data = resp.json() or {}

    # Prefer after-hours trade if present, else last close / deal price
    over = data.get("overMarketPriceInfo") or {}
    price = _parse_kr_number(over.get("overPrice")) if over.get("overMarketStatus") == "OPEN" else None
    if price is None:
        price = _parse_kr_number(
            data.get("closePrice")
            or data.get("dealPrice")
            or data.get("tradePrice")
        )
    if price is None:
        raise MarketDataError(f"Naver returned no price for {code}")

    return {
        "ticker": code,
        "price": float(price),
        "currency": "KRW",
        "updated_at": _now().isoformat(),
        "name": (data.get("stockName") or "").strip() or None,
    }


def fetch_yahoo_price(ticker: str, timeout: float = 15.0) -> dict[str, Any]:
    """Return {ticker, price, currency, updated_at} from Yahoo Finance chart API."""
    symbol = normalize_ticker(ticker)
    if not symbol or symbol in PRIVATE_OR_UNLISTED:
        raise MarketDataError(f"No public quote for {symbol}")
    if is_korean_ticker(symbol):
        raise MarketDataError(f"Korean ticker {symbol} should use Naver, not Yahoo")

    url = YAHOO_CHART.format(ticker=symbol)
    with httpx.Client(timeout=timeout, headers=_UA, follow_redirects=True) as client:
        resp = client.get(url, params={"interval": "1d", "range": "1d"})
        resp.raise_for_status()
        payload = resp.json()

    result = (payload.get("chart") or {}).get("result") or []
    if not result:
        err = ((payload.get("chart") or {}).get("error") or {}).get("description")
        raise MarketDataError(err or f"Yahoo returned no data for {symbol}")

    meta = result[0].get("meta") or {}
    price = meta.get("regularMarketPrice")
    if price is None:
        quote = ((result[0].get("indicators") or {}).get("quote") or [{}])[0]
        closes = quote.get("close") or []
        price = next((c for c in reversed(closes) if c is not None), None)
    if price is None:
        raise MarketDataError(f"No price in Yahoo response for {symbol}")

    currency = meta.get("currency") or "USD"
    name = (meta.get("longName") or meta.get("shortName") or "").strip() or None
    return {
        "ticker": symbol,
        "price": float(price),
        "currency": currency,
        "updated_at": _now().isoformat(),
        "name": name,
    }


def fetch_price(ticker: str, timeout: float = 15.0) -> dict[str, Any]:
    """Route: Korean 6-digit → Naver, otherwise → Yahoo."""
    symbol = normalize_ticker(ticker)
    if is_korean_ticker(symbol):
        return fetch_naver_price(symbol, timeout=timeout)
    return fetch_yahoo_price(symbol, timeout=timeout)


def fetch_usdkrw(timeout: float = 15.0) -> float:
    """USD→KRW mid rate via Frankfurter (ECB)."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(FRANKFURTER_URL, params={"from": "USD", "to": "KRW"})
        resp.raise_for_status()
        data = resp.json()
    rate = (data.get("rates") or {}).get("KRW")
    if rate is None:
        raise MarketDataError("Frankfurter did not return USD/KRW")
    return float(rate)


def is_stale(updated_at: str | datetime | None, stale_hours: float = STALE_HOURS) -> bool:
    if not updated_at:
        return True
    if isinstance(updated_at, str):
        ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    else:
        ts = updated_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    age_h = (_now() - ts).total_seconds() / 3600.0
    return age_h >= stale_hours


def refresh_tickers(tickers: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Fetch prices for tickers (Naver KR / Yahoo US). Returns (rows, errors)."""
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        symbol = normalize_ticker(raw)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        if symbol in PRIVATE_OR_UNLISTED:
            errors.append(f"{symbol}: private/unlisted — skipped")
            continue
        try:
            row = fetch_price(symbol)
            # market_prices table: ticker, price, currency, updated_at
            rows.append(
                {
                    "ticker": row["ticker"],
                    "price": row["price"],
                    "currency": row["currency"],
                    "updated_at": row["updated_at"],
                    "name": row.get("name"),
                }
            )
        except Exception as exc:  # noqa: BLE001 — collect per-ticker failures
            errors.append(f"{symbol}: {exc}")
    return rows, errors


def sync_holding_names(client, price_rows: list[dict[str, Any]]) -> int:
    """Write resolved names from price fetch back onto holdings."""
    updated = 0
    for row in price_rows:
        name = (row.get("name") or "").strip()
        ticker = normalize_ticker(row.get("ticker"))
        if not ticker or not name or name.upper() == ticker:
            continue
        try:
            client.table("holdings").update({"name": name}).eq("ticker", ticker).execute()
            updated += 1
        except Exception:
            continue
    return updated
