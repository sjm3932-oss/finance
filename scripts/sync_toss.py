#!/usr/bin/env python3
"""Sync Toss Securities holdings and filled orders into the couple DB.

Does not place orders. Account trade history comes from GET /api/v1/orders
(not GET /api/v1/trades, which is market ticks).

Prereqs:
  1. tossinvest.com WTS → 설정 → Open API → client_id / client_secret 발급
  2. 같은 화면에서 이 머신의 공인 IP를 허용 IP에 등록
  3. Env: TOSS_CLIENT_ID, TOSS_CLIENT_SECRET, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

Usage:
  python3 scripts/sync_toss.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
load_dotenv(ROOT / ".env")

from sync_revision import SYNC_REVISION  # noqa: E402
from toss_client import (  # noqa: E402
    INSTITUTION,
    TOSS_BASE,
    date_windows,
    estimate_holding_dividends,
    extract_holdings_items,
    extract_orders,
    holdings_by_currency,
    humanize_toss_error,
    local_account_key,
    map_filled_order,
    normalize_ticker,
    pagination_cursor,
    to_number,
)

USER_EMAIL = os.getenv("CLEAR_USER_EMAIL", "sjm3932@gmail.com")
TRADE_LOOKBACK_DAYS = max(1, int(os.getenv("TOSS_TRADE_LOOKBACK_DAYS", "365")))
KST = ZoneInfo("Asia/Seoul")


def supabase():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def public_ip() -> str:
    try:
        with urllib.request.urlopen("https://ifconfig.me/ip", timeout=8) as resp:
            return resp.read().decode().strip()
    except Exception:
        return "(unknown)"


def toss_request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    account_seq: int | None = None,
    query: dict[str, str] | None = None,
    form: dict[str, str] | None = None,
) -> tuple[int, Any]:
    url = TOSS_BASE + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    headers = {"Accept": "application/json"}
    data = None
    if form is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        data = urllib.parse.urlencode(form).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if account_seq is not None:
        headers["X-Tossinvest-Account"] = str(account_seq)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {"raw": raw[:500]}
        return e.code, payload


def issue_token(client_id: str, client_secret: str) -> str:
    status, payload = toss_request(
        "POST",
        "/oauth2/token",
        form={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    token = (payload or {}).get("access_token") if isinstance(payload, dict) else None
    if status != 200 or not token:
        raise RuntimeError(humanize_toss_error(status, payload))
    return str(token)


def ensure_account(c, user_id: str, currency: str) -> str:
    inst, account_type, ccy = local_account_key(currency)
    rows = (
        c.table("accounts")
        .select("id,institution,account_type,currency")
        .eq("user_id", user_id)
        .eq("institution", inst)
        .eq("currency", ccy)
        .execute()
        .data
        or []
    )
    if rows:
        return rows[0]["id"]
    payload = {
        "user_id": user_id,
        "institution": inst,
        "account_type": account_type,
        "currency": ccy,
        "ownership": "mine",
        "cash_balance": 0,
    }
    try:
        res = c.table("accounts").insert(payload).execute()
        if res.data:
            print(f"  + account {inst} {ccy}")
            return res.data[0]["id"]
    except Exception:
        pass
    res = c.table("accounts").insert(
        {
            "user_id": user_id,
            "institution": inst,
            "account_type": account_type,
            "currency": ccy,
        }
    ).execute()
    if not res.data:
        raise SystemExit(f"failed to create {inst} {ccy} account")
    print(f"  + account {inst} {ccy}")
    return res.data[0]["id"]


def upsert_holdings(c, account_id: str, rows: list[dict]) -> None:
    keep: set[str] = set()
    for h in rows:
        keep.add(h["ticker"])
        c.table("holdings").upsert(
            {
                "account_id": account_id,
                "ticker": h["ticker"],
                "name": h["name"],
                "quantity": h["quantity"],
                "avg_price": h["avg_price"],
                "currency": h["currency"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="account_id,ticker",
        ).execute()
        if h.get("last_price"):
            try:
                c.table("market_prices").upsert(
                    {
                        "ticker": h["ticker"],
                        "price": h["last_price"],
                        "currency": h["currency"],
                    },
                    on_conflict="ticker",
                ).execute()
            except Exception as exc:
                print(f"  market_prices skip {h['ticker']}: {exc}")
    existing = c.table("holdings").select("id,ticker").eq("account_id", account_id).execute().data or []
    for row in existing:
        if row["ticker"] not in keep:
            c.table("holdings").delete().eq("id", row["id"]).execute()
            print(f"  - dropped {row['ticker']}")


def set_cash(c, account_id: str, cash: float) -> None:
    try:
        c.table("accounts").update({"cash_balance": cash}).eq("id", account_id).execute()
    except Exception as exc:
        print(f"  cash_balance skip: {exc}")


def _kst_today() -> str:
    return datetime.now(KST).date().isoformat()


def _kst_from(days: int) -> str:
    return (datetime.now(KST).date() - timedelta(days=days)).isoformat()


def _get_orders_page(
    token: str,
    account_seq: int,
    query: dict[str, str],
) -> tuple[int, Any]:
    time.sleep(0.25)
    status, payload = toss_request(
        "GET",
        "/api/v1/orders",
        token=token,
        account_seq=account_seq,
        query=query,
    )
    if status == 429:
        time.sleep(1.5)
        status, payload = toss_request(
            "GET",
            "/api/v1/orders",
            token=token,
            account_seq=account_seq,
            query=query,
        )
    return status, payload


def _collect_order_pages(
    token: str,
    account_seq: int,
    query: dict[str, str],
    *,
    seen: set[str],
    out: list[dict[str, Any]],
) -> str | None:
    """Paginate one getOrders filter. Returns an error string, or None on success."""
    cursor: str | None = None
    last_error = ""
    for _ in range(50):
        page_query = dict(query)
        if cursor:
            page_query["cursor"] = cursor
        status, payload = _get_orders_page(token, account_seq, page_query)
        if status != 200:
            last_error = humanize_toss_error(status, payload)
            return last_error
        for order in extract_orders(payload):
            oid = str(order.get("orderId") or order.get("id") or "")
            if oid and oid in seen:
                continue
            if oid:
                seen.add(oid)
            out.append(order)
        has_next, cursor = pagination_cursor(payload)
        if not has_next or not cursor:
            return None
    return last_error or None


def fetch_account_orders(
    token: str,
    account_seq: int,
    *,
    from_date: str,
    to_date: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """OPEN (working fills) + CLOSED history in ~31-day windows.

    Official docs support CLOSED now; some accounts still 400 `closed-not-supported`.
    Rate limit group ORDER_HISTORY is 5/sec.
    """
    out: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()

    open_err = _collect_order_pages(
        token,
        account_seq,
        {"status": "OPEN"},
        seen=seen,
        out=out,
    )
    if open_err:
        warnings.append(f"OPEN: {open_err}")

    closed_ok = False
    windows = date_windows(from_date, to_date, 31) or [(from_date, to_date)]
    unsupported = False
    for win_from, win_to in windows:
        err = _collect_order_pages(
            token,
            account_seq,
            {
                "status": "CLOSED",
                "from": win_from,
                "to": win_to,
                "limit": "100",
            },
            seen=seen,
            out=out,
        )
        if err:
            warnings.append(f"CLOSED {win_from}~{win_to}: {err}")
            if "CLOSED" in err and "지원하지 않습니다" in err:
                unsupported = True
                break
            continue
        closed_ok = True
    if not closed_ok and not unsupported:
        err = _collect_order_pages(
            token,
            account_seq,
            {"status": "CLOSED", "limit": "100"},
            seen=seen,
            out=out,
        )
        if err:
            warnings.append(f"CLOSED: {err}")
        else:
            closed_ok = True
    return out, warnings


def fetch_closed_orders(
    token: str,
    account_seq: int,
    *,
    from_date: str,
    to_date: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    return fetch_account_orders(
        token, account_seq, from_date=from_date, to_date=to_date
    )


def existing_trade_keys(c, account_ids: list[str]) -> set[str]:
    keys: set[str] = set()
    if not account_ids:
        return keys
    try:
        rows = (
            c.table("trades")
            .select("external_id,reason")
            .in_("account_id", account_ids)
            .execute()
            .data
            or []
        )
    except Exception:
        rows = (
            c.table("trades")
            .select("reason")
            .in_("account_id", account_ids)
            .execute()
            .data
            or []
        )
    for row in rows:
        ext = str(row.get("external_id") or "").strip()
        if ext:
            keys.add(ext)
        reason = str(row.get("reason") or "")
        if reason.startswith("toss:"):
            keys.add(reason[5:])
    return keys


def insert_toss_trades(
    c,
    *,
    user_id: str,
    account_ids: dict[str, str],
    orders: list[dict[str, Any]],
) -> tuple[int, dict[str, int]]:
    """Insert new filled orders. Holdings stay snapshot-authoritative."""
    mapped = [m for o in orders if (m := map_filled_order(o))]
    if not mapped:
        return 0, {}
    known = existing_trade_keys(c, list(account_ids.values()))
    inserted = 0
    per_ccy: dict[str, int] = {}
    for row in mapped:
        ext = row["external_id"]
        if ext in known:
            continue
        ccy = row["currency"]
        account_id = account_ids.get(ccy)
        if not account_id:
            continue
        payload: dict[str, Any] = {
            "account_id": account_id,
            "trade_date": row["trade_date"],
            "ticker": row["ticker"],
            "trade_type": row["trade_type"],
            "price": row["price"],
            "quantity": row["quantity"],
            "fee": row["fee"],
            "currency": ccy,
            "reason": row["reason"],
            "created_by": user_id,
            "adjust_holdings": False,
            "external_id": ext,
        }
        try:
            res = c.table("trades").insert(payload).execute()
        except Exception:
            payload.pop("external_id", None)
            payload["reason"] = f"toss:{ext}"
            try:
                res = c.table("trades").insert(payload).execute()
            except Exception as exc:
                print(f"  trade skip {row['ticker']} {ext[:8]}: {exc}")
                continue
        if res.data:
            inserted += 1
            known.add(ext)
            per_ccy[ccy] = per_ccy.get(ccy, 0) + 1
    return inserted, per_ccy


def existing_dividend_keys(c, account_ids: list[str]) -> set[str]:
    keys: set[str] = set()
    if not account_ids:
        return keys
    try:
        rows = (
            c.table("dividends")
            .select("external_id")
            .in_("account_id", account_ids)
            .execute()
            .data
            or []
        )
    except Exception:
        return keys
    for row in rows:
        ext = str(row.get("external_id") or "").strip()
        if ext:
            keys.add(ext)
    return keys


def insert_toss_dividends(
    c,
    *,
    user_id: str,
    account_ids: dict[str, str],
    rows: list[dict[str, Any]],
) -> dict[str, int]:
    known = existing_dividend_keys(c, list(account_ids.values()))
    per_ccy: dict[str, int] = {}
    for row in rows:
        ext = row["external_id"]
        if ext in known:
            continue
        ccy = row["currency"]
        account_id = account_ids.get(ccy)
        if not account_id:
            continue
        payload: dict[str, Any] = {
            "user_id": user_id,
            "account_id": account_id,
            "ticker": normalize_ticker(row["ticker"]) or row["ticker"],
            "name": row.get("name") or row["ticker"],
            "pay_date": row["pay_date"],
            "amount": row["amount"],
            "currency": ccy,
            "memo": row.get("memo") or "토스 배당(추정)",
            "external_id": ext,
        }
        try:
            res = c.table("dividends").insert(payload).execute()
        except Exception:
            payload.pop("external_id", None)
            try:
                res = c.table("dividends").insert(payload).execute()
            except Exception as exc:
                print(f"  dividend skip {row['ticker']}: {exc}")
                continue
        if res.data:
            known.add(ext)
            per_ccy[ccy] = per_ccy.get(ccy, 0) + 1
    return per_ccy


def run_sync(*, user_id: str | None = None) -> dict:
    client_id = os.getenv("TOSS_CLIENT_ID", "").strip()
    client_secret = os.getenv("TOSS_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError(
            "TOSS_CLIENT_ID / TOSS_CLIENT_SECRET required. "
            "토스증권 WTS → 설정 → Open API 에서 발급하세요."
        )

    ip = public_ip()
    print(f"Public IP (allow-list this in Toss WTS): {ip}")

    c = supabase()
    uid = user_id
    if not uid:
        users = c.table("users").select("id,email").eq("email", USER_EMAIL).execute().data or []
        if not users:
            raise RuntimeError(f"User {USER_EMAIL} not found — log in once first")
        uid = users[0]["id"]

    token = issue_token(client_id, client_secret)
    print("Token ok")

    status, payload = toss_request("GET", "/api/v1/accounts", token=token)
    if status != 200:
        raise RuntimeError(humanize_toss_error(status, payload))
    accounts = (payload or {}).get("result") or []
    brokerage = [a for a in accounts if a.get("accountType") in (None, "BROKERAGE")]
    if not brokerage:
        brokerage = accounts
    if not brokerage:
        raise RuntimeError("토스 계좌가 없습니다. Open API에 계좌가 연결되어 있는지 확인하세요.")

    fx_status, fx_payload = toss_request(
        "GET",
        "/api/v1/exchange-rate",
        token=token,
        query={"baseCurrency": "USD", "quoteCurrency": "KRW"},
    )
    if fx_status == 200:
        rate = ((fx_payload or {}).get("result") or {}).get("midRate") or (
            (fx_payload or {}).get("result") or {}
        ).get("rate")
        if rate:
            c.table("market_prices").upsert(
                {"ticker": "USDKRW", "price": to_number(rate), "currency": "KRW"},
                on_conflict="ticker",
            ).execute()
            print(f"  USDKRW={rate}")
    else:
        print(f"  exchange-rate skip: {humanize_toss_error(fx_status, fx_payload)}")

    summary: list[dict] = []
    total_rows = 0
    for i, acct in enumerate(brokerage):
        seq = acct.get("accountSeq")
        if seq is None:
            continue
        if i:
            time.sleep(1.1)
        hs, hp = toss_request("GET", "/api/v1/holdings", token=token, account_seq=int(seq))
        if hs != 200:
            raise RuntimeError(humanize_toss_error(hs, hp))
        items = extract_holdings_items(hp)
        by_ccy = holdings_by_currency(items)

        cash = {"KRW": 0.0, "USD": 0.0}
        for ccy in ("KRW", "USD"):
            cs, cp = toss_request(
                "GET",
                "/api/v1/buying-power",
                token=token,
                account_seq=int(seq),
                query={"currency": ccy},
            )
            if cs == 200:
                cash[ccy] = to_number(((cp or {}).get("result") or {}).get("cashBuyingPower"))
            else:
                print(f"  buying-power {ccy} skip: {humanize_toss_error(cs, cp)}")

        from_date = _kst_from(TRADE_LOOKBACK_DAYS)
        to_date = _kst_today()
        order_warnings: list[str] = []
        try:
            raw_orders, order_warnings = fetch_account_orders(
                token,
                int(seq),
                from_date=from_date,
                to_date=to_date,
            )
        except Exception as exc:
            print(f"  orders skip: {exc}")
            raw_orders = []
            order_warnings.append(str(exc))
        for w in order_warnings:
            print(f"  orders warn: {w}")

        filled = [m for o in raw_orders if (m := map_filled_order(o))]
        trade_ccy = {m["currency"] for m in filled}
        all_holdings = (by_ccy.get("KRW") or []) + (by_ccy.get("USD") or [])
        try:
            raw_divs = estimate_holding_dividends(
                all_holdings, from_date=from_date, to_date=to_date, source="toss"
            )
        except Exception as exc:
            print(f"  dividends skip: {exc}")
            raw_divs = []
        div_ccy = {d["currency"] for d in raw_divs}

        account_ids: dict[str, str] = {}
        for ccy in ("KRW", "USD"):
            rows = by_ccy.get(ccy) or []
            if not rows and cash[ccy] <= 0 and ccy not in trade_ccy and ccy not in div_ccy:
                continue
            aid = ensure_account(c, uid, ccy)
            account_ids[ccy] = aid
            upsert_holdings(c, aid, rows)
            set_cash(c, aid, cash[ccy])
            total_rows += len(rows)

        inserted_by_ccy: dict[str, int] = {}
        trades_n = 0
        if account_ids and raw_orders:
            trades_n, inserted_by_ccy = insert_toss_trades(
                c, user_id=uid, account_ids=account_ids, orders=raw_orders
            )
        divs_by_ccy: dict[str, int] = {}
        if account_ids and raw_divs:
            divs_by_ccy = insert_toss_dividends(
                c, user_id=uid, account_ids=account_ids, rows=raw_divs
            )

        for ccy, _aid in account_ids.items():
            rows = by_ccy.get(ccy) or []
            summary.append(
                {
                    "currency": ccy,
                    "holdings": len(rows),
                    "cash": cash[ccy],
                    "trades": inserted_by_ccy.get(ccy, 0),
                    "dividends": divs_by_ccy.get(ccy, 0),
                    "mapped_trades": sum(1 for m in filled if m["currency"] == ccy),
                }
            )
            print(
                f"  {INSTITUTION} {ccy}: {len(rows)} holdings, cash={cash[ccy]}, "
                f"체결 {inserted_by_ccy.get(ccy, 0)}건, 배당 {divs_by_ccy.get(ccy, 0)}건"
            )

        if trades_n:
            print(f"  {INSTITUTION} filled orders inserted: {trades_n}")
        if sum(divs_by_ccy.values()):
            print(f"  {INSTITUTION} dividends inserted: {sum(divs_by_ccy.values())}")

    trades_total = sum(int(a.get("trades") or 0) for a in summary)
    divs_total = sum(int(a.get("dividends") or 0) for a in summary)
    print(f"Done. Synced {total_rows} holdings into {INSTITUTION}.")
    return {
        "ok": True,
        "institution": INSTITUTION,
        "accounts": summary,
        "egress_ip": ip,
        "trades": trades_total,
        "dividends": divs_total,
        "sync_revision": SYNC_REVISION,
    }


def main() -> None:
    try:
        run_sync()
    except Exception as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
    sys.exit(0)
