"""Market price + FX helpers (Yahoo / Frankfurter — no paid keys required)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx

# Tickers that are not on public markets
PRIVATE_OR_UNLISTED = {"SPACEX", "PRIVATE"}

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"
STALE_HOURS = float(os.getenv("MARKET_PRICE_STALE_HOURS", "24"))


class MarketDataError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def fetch_yahoo_price(ticker: str, timeout: float = 15.0) -> dict[str, Any]:
    """Return {ticker, price, currency, updated_at} from Yahoo Finance chart API."""
    symbol = ticker.strip().upper()
    if not symbol or symbol in PRIVATE_OR_UNLISTED:
        raise MarketDataError(f"No public quote for {symbol}")

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; CouplesWealthMaster/1.0)",
    }
    url = YAHOO_CHART.format(ticker=symbol)
    with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
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
        # fall back to last close in indicators
        quote = ((result[0].get("indicators") or {}).get("quote") or [{}])[0]
        closes = quote.get("close") or []
        price = next((c for c in reversed(closes) if c is not None), None)
    if price is None:
        raise MarketDataError(f"No price in Yahoo response for {symbol}")

    currency = meta.get("currency") or "USD"
    return {
        "ticker": symbol,
        "price": float(price),
        "currency": currency,
        "updated_at": _now().isoformat(),
    }


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
    """Fetch prices for tickers. Returns (rows, errors)."""
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        symbol = (raw or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        if symbol in PRIVATE_OR_UNLISTED:
            errors.append(f"{symbol}: private/unlisted — skipped")
            continue
        try:
            rows.append(fetch_yahoo_price(symbol))
        except Exception as exc:  # noqa: BLE001 — collect per-ticker failures
            errors.append(f"{symbol}: {exc}")
    return rows, errors
