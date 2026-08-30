#!/usr/bin/env python3
"""Sync Toss Securities holdings into the couple DB (no orders).

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
load_dotenv(ROOT / ".env")

from toss_client import (  # noqa: E402
    INSTITUTION,
    TOSS_BASE,
    holdings_by_currency,
    humanize_toss_error,
    local_account_key,
    to_number,
)

USER_EMAIL = os.getenv("CLEAR_USER_EMAIL", "sjm3932@gmail.com")


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
        "ownership": "joint",
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
        items = ((hp or {}).get("result") or {}).get("items") or []
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

        for ccy, rows in by_ccy.items():
            if not rows and cash[ccy] <= 0:
                continue
            aid = ensure_account(c, uid, ccy)
            upsert_holdings(c, aid, rows)
            set_cash(c, aid, cash[ccy])
            total_rows += len(rows)
            summary.append({"currency": ccy, "holdings": len(rows), "cash": cash[ccy]})
            print(f"  {INSTITUTION} {ccy}: {len(rows)} holdings, cash={cash[ccy]}")

    print(f"Done. Synced {total_rows} holdings into {INSTITUTION}.")
    return {"ok": True, "institution": INSTITUTION, "accounts": summary, "egress_ip": ip}


def main() -> None:
    try:
        run_sync()
    except Exception as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
    sys.exit(0)
