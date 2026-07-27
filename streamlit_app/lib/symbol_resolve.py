"""Resolve missing ticker ↔ 종목명 for OCR rows (Naver / Yahoo / holdings)."""

from __future__ import annotations

import re
from typing import Any

import httpx

_UA = {"User-Agent": "Mozilla/5.0 (compatible; Bujattung/1.0)"}
_KR_CODE = re.compile(r"^\d{6}$")
_YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
_NAVER_BASIC = "https://m.stock.naver.com/api/stock/{code}/basic"
_NAVER_SEARCH = "https://m.stock.naver.com/front-api/search/autoComplete"
_YAHOO_SEARCH = "https://query1.finance.yahoo.com/v1/finance/search"

_ROW_KEYS = ("trades", "dividends", "holdings_snapshot")


def _norm_ticker(raw: Any) -> str:
    t = str(raw or "").strip().upper()
    if t.endswith(".KS") or t.endswith(".KQ"):
        base = t[:-3]
        if _KR_CODE.match(base):
            return base
    return t


def _norm_name(raw: Any) -> str:
    return str(raw or "").strip()


def _is_blank(v: Any) -> bool:
    return not str(v or "").strip()


def name_is_missing(ticker: Any, name: Any) -> bool:
    """True when name is empty, equals ticker, or is itself a 6-digit code."""
    t = _norm_ticker(ticker)
    n = _norm_name(name)
    if not n:
        return True
    if t and n.upper() == t:
        return True
    if _looks_kr_code(n):
        return True
    return False


def _looks_kr_code(ticker: str) -> bool:
    return bool(_KR_CODE.match(ticker))


def _holdings_maps(client) -> tuple[dict[str, str], dict[str, str]]:
    """ticker→name and name→ticker from existing holdings."""
    by_ticker: dict[str, str] = {}
    by_name: dict[str, str] = {}
    if client is None:
        return by_ticker, by_name
    try:
        rows = client.table("holdings").select("ticker,name").execute().data or []
    except Exception:
        return by_ticker, by_name
    for r in rows:
        t = _norm_ticker(r.get("ticker"))
        n = _norm_name(r.get("name"))
        if t and n and n.upper() != t and not _looks_kr_code(n):
            by_ticker.setdefault(t, n)
            by_name.setdefault(n.lower(), t)
    return by_ticker, by_name


def _naver_name(code: str, timeout: float = 8.0) -> str | None:
    try:
        with httpx.Client(timeout=timeout, headers=_UA, follow_redirects=True) as client:
            resp = client.get(_NAVER_BASIC.format(code=code))
            resp.raise_for_status()
            data = resp.json() or {}
        name = _norm_name(data.get("stockName") or data.get("stock_name"))
        return name or None
    except Exception:
        return None


def _naver_ticker(name: str, timeout: float = 8.0) -> str | None:
    try:
        with httpx.Client(timeout=timeout, headers=_UA, follow_redirects=True) as client:
            resp = client.get(
                _NAVER_SEARCH,
                params={"query": name, "target": "stock"},
            )
            resp.raise_for_status()
            payload = resp.json() or {}
        items = ((payload.get("result") or {}).get("items")) or []
        if not items:
            return None
        q = name.lower()
        exact = [
            it
            for it in items
            if _norm_name(it.get("name")).lower() == q and it.get("category") == "stock"
        ]
        pool = exact or [it for it in items if it.get("category") == "stock"] or items
        code = _norm_ticker(pool[0].get("code") or pool[0].get("reutersCode"))
        return code or None
    except Exception:
        return None


def _yahoo_name(ticker: str, timeout: float = 8.0) -> str | None:
    candidates = [ticker]
    if _looks_kr_code(ticker):
        candidates = [f"{ticker}.KS", f"{ticker}.KQ", ticker]
    try:
        with httpx.Client(timeout=timeout, headers=_UA, follow_redirects=True) as client:
            for sym in candidates:
                try:
                    resp = client.get(
                        _YAHOO_CHART.format(ticker=sym),
                        params={"interval": "1d", "range": "1d"},
                    )
                    resp.raise_for_status()
                    result = ((resp.json().get("chart") or {}).get("result") or [])
                    if not result:
                        continue
                    meta = result[0].get("meta") or {}
                    name = _norm_name(meta.get("shortName") or meta.get("longName"))
                    if name:
                        return name
                except Exception:
                    continue
    except Exception:
        return None
    return None


def _yahoo_ticker(name: str, timeout: float = 8.0) -> str | None:
    # Hangul queries often 400 on Yahoo — skip obvious KR-only names
    if re.search(r"[\uac00-\ud7a3]", name) and not re.search(r"[A-Za-z]", name):
        return None
    try:
        with httpx.Client(timeout=timeout, headers=_UA, follow_redirects=True) as client:
            resp = client.get(
                _YAHOO_SEARCH,
                params={"q": name, "quotesCount": 8, "newsCount": 0},
            )
            resp.raise_for_status()
            quotes = (resp.json().get("quotes") or [])
    except Exception:
        return None
    if not quotes:
        return None
    preferred = [
        q
        for q in quotes
        if (q.get("quoteType") in ("EQUITY", "ETF"))
        and (q.get("exchDisp") in ("NASDAQ", "NYSE", "NYSEArca", "AMEX", "Korea", None) or True)
    ]
    pool = preferred or quotes
    sym = _norm_ticker(pool[0].get("symbol"))
    return sym or None


def resolve_name_for_ticker(
    ticker: str,
    *,
    by_ticker: dict[str, str] | None = None,
    cache: dict[str, str] | None = None,
) -> str | None:
    t = _norm_ticker(ticker)
    if not t:
        return None
    if by_ticker and t in by_ticker:
        return by_ticker[t]
    if cache is not None and f"n:{t}" in cache:
        return cache[f"n:{t}"] or None

    name = None
    if _looks_kr_code(t):
        name = _naver_name(t) or _yahoo_name(t)
    else:
        name = _yahoo_name(t) or _naver_name(t)
    if cache is not None:
        cache[f"n:{t}"] = name or ""
    return name


def resolve_ticker_for_name(
    name: str,
    *,
    by_name: dict[str, str] | None = None,
    cache: dict[str, str] | None = None,
) -> str | None:
    n = _norm_name(name)
    if not n:
        return None
    key = n.lower()
    if by_name and key in by_name:
        return by_name[key]
    if cache is not None and f"t:{key}" in cache:
        return cache[f"t:{key}"] or None

    ticker = _naver_ticker(n) or _yahoo_ticker(n)
    if cache is not None:
        cache[f"t:{key}"] = ticker or ""
    return ticker


def enrich_symbol_row(
    row: dict[str, Any],
    *,
    by_ticker: dict[str, str],
    by_name: dict[str, str],
    cache: dict[str, str],
) -> dict[str, Any]:
    out = dict(row)
    ticker = _norm_ticker(out.get("ticker"))
    name = _norm_name(out.get("name"))

    if ticker and name_is_missing(ticker, name):
        filled = resolve_name_for_ticker(ticker, by_ticker=by_ticker, cache=cache)
        if filled:
            name = filled
    if name and _is_blank(ticker):
        filled = resolve_ticker_for_name(name, by_name=by_name, cache=cache)
        if filled:
            ticker = filled

    if ticker:
        out["ticker"] = ticker
    if name:
        out["name"] = name
    return out


def enrich_holdings_names(
    client,
    holdings: list[dict[str, Any]],
    *,
    persist: bool = True,
) -> list[dict[str, Any]]:
    """Fill missing 종목명 on holdings rows (Naver/Yahoo) and optionally persist."""
    if not holdings:
        return holdings
    by_ticker, _by_name = _holdings_maps(client)
    cache: dict[str, str] = {}
    out: list[dict[str, Any]] = []
    persisted: set[str] = set()

    for h in holdings:
        row = dict(h)
        ticker = _norm_ticker(row.get("ticker"))
        if ticker and name_is_missing(ticker, row.get("name")):
            filled = resolve_name_for_ticker(
                ticker, by_ticker=by_ticker, cache=cache
            )
            if filled:
                row["name"] = filled
                by_ticker[ticker] = filled
                if persist and client is not None and ticker not in persisted:
                    persisted.add(ticker)
                    try:
                        # Update every account row for this ticker
                        client.table("holdings").update({"name": filled}).eq(
                            "ticker", ticker
                        ).execute()
                        raw = str(h.get("ticker") or "").strip()
                        if raw and raw != ticker:
                            client.table("holdings").update({"name": filled}).eq(
                                "ticker", raw
                            ).execute()
                    except Exception:
                        pass
        out.append(row)
    return out


def enrich_parsed_symbols(parsed: dict[str, Any], client=None) -> dict[str, Any]:
    """Fill missing ticker/name on trades, dividends, holdings_snapshot."""
    if not isinstance(parsed, dict):
        return parsed
    by_ticker, by_name = _holdings_maps(client)
    cache: dict[str, str] = {}
    out = dict(parsed)
    for key in _ROW_KEYS:
        rows = out.get(key)
        if not isinstance(rows, list):
            continue
        out[key] = [
            enrich_symbol_row(r, by_ticker=by_ticker, by_name=by_name, cache=cache)
            if isinstance(r, dict)
            else r
            for r in rows
        ]
    return out
