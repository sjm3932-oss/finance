#!/usr/bin/env python3
"""Sync Korea Investment holdings, fills, and dividends into the couple DB.

Does not place orders.

Prereqs:
  1. KIS Developers (https://apiportal.koreainvestment.com) 에서 앱키 발급
     — 포털 가입 때 휴대폰 인증이 한 번 필요합니다. API 호출마다 인증하지는 않습니다.
  2. 앱 기록하기 → 한투 동기화에 앱키·시크릿·계좌를 저장 (또는 env)
    3. Env (optional override):
       KIS_APP_KEY, KIS_APP_SECRET
       KIS_CANO (8자리) + KIS_ACNT_PRDT_CD (기본 01)
       또는 KIS_ACCOUNTS=12345678-01,12345678-22
       SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
       선택: KIS_ENV=real|demo, KIS_TRADE_LOOKBACK_DAYS=365

Usage:
  python3 scripts/sync_kis.py
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

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
load_dotenv(ROOT / ".env")

from kis_client import (  # noqa: E402
    INSTITUTION,
    date_windows,
    domestic_cash,
    fmt_yyyymmdd,
    holdings_by_currency,
    humanize_kis_error,
    is_demo,
    is_rate_limited,
    kis_base,
    lookback_range,
    memo_product_code,
    product_label,
    product_memo,
    ISA_FUND_HOLDING_NAME,
    ISA_FUND_TICKER,
    map_domestic_dividend,
    map_domestic_fill,
    map_domestic_holding,
    map_overseas_fill,
    map_overseas_holding,
    merge_credentials,
    merge_estimated_dividends,
    normalize_kr_ticker,
    output_rows,
    overseas_cash,
    to_number,
)
from toss_client import estimate_holding_dividends  # noqa: E402
from sync_revision import SYNC_REVISION  # noqa: E402

USER_EMAIL = os.getenv("CLEAR_USER_EMAIL", "sjm3932@gmail.com")
TRADE_LOOKBACK_DAYS = max(1, int(os.getenv("KIS_TRADE_LOOKBACK_DAYS", "365")))
TOKEN_PATH = Path(os.getenv("KIS_TOKEN_PATH", "/tmp/kis_access_token.json"))


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


def _json_body(raw: str) -> Any:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw[:500]}


def kis_request(
    method: str,
    path: str,
    *,
    base: str,
    appkey: str,
    appsecret: str,
    token: str | None = None,
    tr_id: str | None = None,
    tr_cont: str = "",
    query: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> tuple[int, Any, dict[str, str]]:
    url = base + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "appkey": appkey,
        "appsecret": appsecret,
        "custtype": "P",
    }
    if token:
        headers["authorization"] = f"Bearer {token}"
    if tr_id:
        headers["tr_id"] = tr_id
    if tr_cont:
        headers["tr_cont"] = tr_cont
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            body = resp.read().decode()
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, _json_body(body), hdrs
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        hdrs = {k.lower(): v for k, v in e.headers.items()} if e.headers else {}
        return e.code, _json_body(raw), hdrs


def _token_until(expires_in: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in - 60))


def _load_cached_token() -> str | None:
    try:
        data = json.loads(TOKEN_PATH.read_text())
    except Exception:
        return None
    token = str(data.get("access_token") or "")
    exp = str(data.get("expires_at") or "")
    if not token:
        return None
    try:
        until = datetime.fromisoformat(exp)
    except Exception:
        return token
    if datetime.now(timezone.utc) + timedelta(minutes=5) >= until:
        return None
    return token


def _save_cached_token(token: str, expires_in: int) -> None:
    until = _token_until(expires_in)
    try:
        TOKEN_PATH.write_text(
            json.dumps({"access_token": token, "expires_at": until.isoformat()})
        )
    except Exception:
        pass


def _load_db_token(c) -> str | None:
    try:
        rows = (
            c.table("kis_api_settings")
            .select("access_token,token_expires_at")
            .eq("id", 1)
            .execute()
            .data
            or []
        )
    except Exception:
        return None
    if not rows:
        return None
    token = str(rows[0].get("access_token") or "").strip()
    if not token:
        return None
    exp = rows[0].get("token_expires_at")
    if not exp:
        return token
    try:
        until = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
    except Exception:
        return token
    if datetime.now(timezone.utc) + timedelta(minutes=5) >= until:
        return None
    return token


def _save_db_token(c, token: str, expires_in: int) -> None:
    if c is None:
        return
    until = _token_until(expires_in)
    try:
        c.table("kis_api_settings").update(
            {"access_token": token, "token_expires_at": until.isoformat()}
        ).eq("id", 1).execute()
    except Exception:
        pass


def issue_token(appkey: str, appsecret: str, base: str, *, db=None) -> str:
    cached = _load_cached_token() or _load_db_token(db)
    if cached:
        return cached
    status, payload, _hdrs = kis_request(
        "POST",
        "/oauth2/tokenP",
        base=base,
        appkey=appkey,
        appsecret=appsecret,
        json_body={
            "grant_type": "client_credentials",
            "appkey": appkey,
            "appsecret": appsecret,
        },
    )
    token = ""
    if isinstance(payload, dict):
        token = str(payload.get("access_token") or "")
        expires_in = int(to_number(payload.get("expires_in") or 86400))
    else:
        expires_in = 86400
    if status == 200 and token:
        _save_cached_token(token, expires_in)
        _save_db_token(db, token, expires_in)
        return token
    # EGW00133: already issued — wait briefly and retry once.
    time.sleep(1.2)
    cached = _load_cached_token() or _load_db_token(db)
    if cached:
        return cached
    status, payload, _hdrs = kis_request(
        "POST",
        "/oauth2/tokenP",
        base=base,
        appkey=appkey,
        appsecret=appsecret,
        json_body={
            "grant_type": "client_credentials",
            "appkey": appkey,
            "appsecret": appsecret,
        },
    )
    token = str((payload or {}).get("access_token") or "") if isinstance(payload, dict) else ""
    if status == 200 and token:
        exp = int(to_number((payload or {}).get("expires_in") or 86400)) if isinstance(payload, dict) else 86400
        _save_cached_token(token, exp)
        _save_db_token(db, token, exp)
        return token
    raise RuntimeError(humanize_kis_error(status, payload))


def paged_get(
    *,
    path: str,
    tr_id: str,
    query: dict[str, str],
    base: str,
    appkey: str,
    appsecret: str,
    token: str,
    fk_key: str,
    nk_key: str,
    output_key: str = "output1",
    extra_output: str | None = None,
    max_pages: int = 40,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    rows: list[dict[str, Any]] = []
    summary: dict[str, Any] | None = None
    tr_cont = ""
    q = dict(query)
    for i in range(max_pages):
        if i:
            time.sleep(0.25)
        status, payload, hdrs = kis_request(
            "GET",
            path,
            base=base,
            appkey=appkey,
            appsecret=appsecret,
            token=token,
            tr_id=tr_id,
            tr_cont=tr_cont,
            query=q,
        )
        retries = 0
        while is_rate_limited(status, payload) and retries < 4:
            time.sleep(1.2 + retries)
            retries += 1
            status, payload, hdrs = kis_request(
                "GET",
                path,
                base=base,
                appkey=appkey,
                appsecret=appsecret,
                token=token,
                tr_id=tr_id,
                tr_cont=tr_cont,
                query=q,
            )
        if status != 200 or (isinstance(payload, dict) and str(payload.get("rt_cd") or "0") not in {"0", "0.0"}):
            raise RuntimeError(humanize_kis_error(status, payload))
        rows.extend(output_rows(payload, output_key, "output"))
        extra = output_rows(payload, extra_output or "output2")
        if extra:
            summary = extra[0]
        tr_cont_hdr = (hdrs.get("tr_cont") or "").strip()
        if isinstance(payload, dict):
            q[fk_key] = str(payload.get(fk_key.lower()) or payload.get(fk_key) or "")
            q[nk_key] = str(payload.get(nk_key.lower()) or payload.get(nk_key) or "")
        if tr_cont_hdr not in {"M", "F"}:
            break
        tr_cont = "N"
    return rows, summary


def ensure_account(c, user_id: str, currency: str, prod: str) -> str:
    rows = (
        c.table("accounts")
        .select("id,institution,account_type,currency,memo")
        .eq("user_id", user_id)
        .eq("institution", INSTITUTION)
        .eq("currency", currency)
        .execute()
        .data
        or []
    )
    for row in rows:
        if memo_product_code(row.get("memo")) == prod:
            return row["id"]
    leftover = next((row for row in rows if memo_product_code(row.get("memo")) is None), None)
    if leftover:
        aid = leftover["id"]
        set_product_account_memo(c, aid, prod)
        print(f"  reuse {INSTITUTION} {currency} as {prod}")
        return aid
    payload = {
        "user_id": user_id,
        "institution": INSTITUTION,
        "account_type": "brokerage",
        "currency": currency,
        "ownership": "mine",
        "cash_balance": 0,
        "memo": product_memo(prod),
    }
    try:
        res = c.table("accounts").insert(payload).execute()
        if res.data:
            print(f"  + account {INSTITUTION} {prod} {currency}")
            return res.data[0]["id"]
    except Exception:
        pass
    res = c.table("accounts").insert(
        {
            "user_id": user_id,
            "institution": INSTITUTION,
            "account_type": "brokerage",
            "currency": currency,
            "memo": product_memo(prod),
        }
    ).execute()
    if not res.data:
        raise SystemExit(f"failed to create {INSTITUTION} {prod} {currency} account")
    print(f"  + account {INSTITUTION} {prod} {currency}")
    return res.data[0]["id"]


def set_product_account_memo(c, account_id: str, prod: str) -> None:
    try:
        c.table("accounts").update({"memo": product_memo(prod)}).eq("id", account_id).execute()
    except Exception as exc:
        print(f"  account memo skip: {exc}")


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
        if reason.startswith("kis:"):
            keys.add(reason)
    return keys


def existing_dividend_keys(c, account_ids: list[str]) -> tuple[set[str], set[str]]:
    keys: set[str] = set()
    if not account_ids:
        return keys, set()
    try:
        rows = (
            c.table("dividends")
            .select("external_id,ticker,pay_date")
            .in_("account_id", account_ids)
            .execute()
            .data
            or []
        )
    except Exception:
        return keys, set()
    pays: set[str] = set()
    for row in rows:
        ext = str(row.get("external_id") or "").strip()
        if ext:
            keys.add(ext)
        ticker = normalize_kr_ticker(row.get("ticker")) or str(row.get("ticker") or "").strip()
        pay = str(row.get("pay_date") or "")[:10]
        if ticker and pay:
            pays.add(f"{ticker}|{pay}")
    return keys, pays


def insert_trades(c, *, user_id: str, account_ids: dict[str, str], rows: list[dict]) -> dict[str, int]:
    known = existing_trade_keys(c, list(account_ids.values()))
    per_ccy: dict[str, int] = {}
    for row in rows:
        ext = row["external_id"]
        if ext in known:
            continue
        ccy = row["currency"]
        prod = str(row.get("product") or "")
        account_id = account_ids.get(f"{prod}:{ccy}") if prod else None
        account_id = account_id or account_ids.get(ccy)
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
            payload["reason"] = ext
            try:
                res = c.table("trades").insert(payload).execute()
            except Exception as exc:
                print(f"  trade skip {row['ticker']} {ext[-12:]}: {exc}")
                continue
        if res.data:
            known.add(ext)
            per_ccy[ccy] = per_ccy.get(ccy, 0) + 1
    return per_ccy


def insert_dividends(c, *, user_id: str, account_ids: dict[str, str], rows: list[dict]) -> dict[str, int]:
    known, have_pay = existing_dividend_keys(c, list(account_ids.values()))
    per_ccy: dict[str, int] = {}
    for row in rows:
        ext = row["external_id"]
        if ext in known:
            continue
        ticker = normalize_kr_ticker(row["ticker"]) or row["ticker"]
        pay_key = f"{ticker}|{row['pay_date']}"
        if pay_key in have_pay:
            continue
        ccy = row["currency"]
        prod = str(row.get("product") or "")
        account_id = account_ids.get(f"{prod}:{ccy}") if prod else None
        account_id = account_id or account_ids.get(ccy)
        if not account_id:
            continue
        payload: dict[str, Any] = {
            "user_id": user_id,
            "account_id": account_id,
            "ticker": ticker,
            "name": row["name"],
            "pay_date": row["pay_date"],
            "amount": row["amount"],
            "currency": ccy,
            "memo": row.get("memo") or "한투 배당",
            "external_id": ext,
        }
        try:
            res = c.table("dividends").insert(payload).execute()
        except Exception:
            payload.pop("external_id", None)
            try:
                res = c.table("dividends").insert(payload).execute()
            except Exception as exc:
                print(f"  dividend skip {row['ticker']} {ext[-12:]}: {exc}")
                continue
        if res.data:
            known.add(ext)
            have_pay.add(pay_key)
            per_ccy[ccy] = per_ccy.get(ccy, 0) + 1
    return per_ccy


def fetch_domestic_balance(ctx: dict, cano: str, prod: str) -> tuple[list[dict], float]:
    query = {
        "CANO": cano,
        "ACNT_PRDT_CD": prod,
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "00",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    tr_id = "VTTC8434R" if is_demo(ctx["env"]) else "TTTC8434R"
    try:
        rows, summary = paged_get(
            path="/uapi/domestic-stock/v1/trading/inquire-balance",
            tr_id=tr_id,
            query=query,
            base=ctx["base"],
            appkey=ctx["appkey"],
            appsecret=ctx["appsecret"],
            token=ctx["token"],
            fk_key="CTX_AREA_FK100",
            nk_key="CTX_AREA_NK100",
            output_key="output1",
            extra_output="output2",
        )
    except RuntimeError as exc:
        if "위탁계좌인 경우만" not in str(exc) and "APAC0489" not in str(exc):
            raise
        try:
            rows, summary = paged_get(
                path="/uapi/domestic-stock/v1/trading/pension/inquire-balance",
                tr_id="TTTC2208R",
                query={
                    "CANO": cano,
                    "ACNT_PRDT_CD": prod,
                    "ACCA_DVSN_CD": "00",
                    "INQR_DVSN": "00",
                    "CTX_AREA_FK100": "",
                    "CTX_AREA_NK100": "",
                },
                base=ctx["base"],
                appkey=ctx["appkey"],
                appsecret=ctx["appsecret"],
                token=ctx["token"],
                fk_key="CTX_AREA_FK100",
                nk_key="CTX_AREA_NK100",
                output_key="output1",
                extra_output="output2",
            )
        except Exception as exc2:
            print(f"  pension balance skip {cano}-{prod}: {exc2}")
            return [], 0.0
    mapped = [m for r in rows if (m := map_domestic_holding(r))]
    return mapped, domestic_cash(summary)


def fetch_account_overview(ctx: dict, cano: str, prod: str) -> dict[str, float]:
    """투자계좌자산현황 — 펀드처럼 종목 API가 안 주는 금액을 잡는다.

    CTRP6548R: nass_tot_amt / evlu_amt_smtl = 펀드·주식 평가액.
    CMA는 tot_asst_amt = nass + cma 로 따로 온다. 빼면 안 된다.
    """
    query = {"CANO": cano, "ACNT_PRDT_CD": prod}
    status, payload, _hdrs = kis_request(
        "GET",
        "/uapi/domestic-stock/v1/trading/inquire-account-balance",
        base=ctx["base"],
        appkey=ctx["appkey"],
        appsecret=ctx["appsecret"],
        token=ctx["token"],
        tr_id="CTRP6548R",
        query=query,
    )
    retries = 0
    while is_rate_limited(status, payload) and retries < 4:
        time.sleep(1.2 + retries)
        retries += 1
        status, payload, _hdrs = kis_request(
            "GET",
            "/uapi/domestic-stock/v1/trading/inquire-account-balance",
            base=ctx["base"],
            appkey=ctx["appkey"],
            appsecret=ctx["appsecret"],
            token=ctx["token"],
            tr_id="CTRP6548R",
            query=query,
        )
    if status != 200 or (
        isinstance(payload, dict) and str(payload.get("rt_cd") or "0") not in {"0", "0.0"}
    ):
        print(f"  account overview skip {cano}-{prod}: {humanize_kis_error(status, payload)}")
        return {"nass": 0.0, "cash": 0.0, "ok": 0.0}
    extra = output_rows(payload, "output2")
    summary = extra[0] if extra else {}
    nass = to_number((summary or {}).get("nass_tot_amt") or (summary or {}).get("evlu_amt_smtl"))
    cash = to_number((summary or {}).get("cma_evlu_amt")) or to_number(
        (summary or {}).get("tot_dncl_amt")
    )
    if nass <= 0:
        for row in output_rows(payload, "output1"):
            nass = max(nass, to_number(row.get("evlu_amt") or row.get("real_nass_amt")))
    print(f"  overview {cano}-{prod}: nass={nass} cash={cash}")
    return {"nass": nass, "cash": cash, "ok": 1.0}


ISA_OTHER_ASSET_NAME = "한국투자증권 ISA(21) 펀드"


def delete_isa_other_asset(c, user_id: str) -> None:
    """ISA fund now lives on the 21 brokerage account; drop the old 기타자산 row."""
    rows = (
        c.table("other_assets")
        .select("id")
        .eq("user_id", user_id)
        .eq("name", ISA_OTHER_ASSET_NAME)
        .execute()
        .data
        or []
    )
    if rows:
        c.table("other_assets").delete().eq("id", rows[0]["id"]).execute()


def fetch_overseas_balance(ctx: dict, cano: str, prod: str) -> list[dict]:
    tr_id = "VTTS3012R" if is_demo(ctx["env"]) else "TTTS3012R"
    rows, _summary = paged_get(
        path="/uapi/overseas-stock/v1/trading/inquire-balance",
        tr_id=tr_id,
        query={
            "CANO": cano,
            "ACNT_PRDT_CD": prod,
            "OVRS_EXCG_CD": "NASD",
            "TR_CRCY_CD": "USD",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": "",
        },
        base=ctx["base"],
        appkey=ctx["appkey"],
        appsecret=ctx["appsecret"],
        token=ctx["token"],
        fk_key="CTX_AREA_FK200",
        nk_key="CTX_AREA_NK200",
        output_key="output1",
        extra_output="output2",
    )
    return [m for r in rows if (m := map_overseas_holding(r))]


def fetch_overseas_cash(ctx: dict, cano: str, prod: str) -> float:
    tr_id = "VTRP6504R" if is_demo(ctx["env"]) else "CTRP6504R"
    try:
        _holdings, _summary = paged_get(
            path="/uapi/overseas-stock/v1/trading/inquire-present-balance",
            tr_id=tr_id,
            query={
                "CANO": cano,
                "ACNT_PRDT_CD": prod,
                "WCRC_FRCR_DVSN_CD": "02",
                "NATN_CD": "000",
                "TR_MKET_CD": "00",
                "INQR_DVSN_CD": "00",
            },
            base=ctx["base"],
            appkey=ctx["appkey"],
            appsecret=ctx["appsecret"],
            token=ctx["token"],
            fk_key="CTX_AREA_FK200",
            nk_key="CTX_AREA_NK200",
            output_key="output2",
            extra_output="output3",
            max_pages=1,
        )
    except Exception as exc:
        print(f"  overseas cash skip: {exc}")
        return 0.0
    return overseas_cash(_holdings, "USD")


def fetch_domestic_fills(ctx: dict, cano: str, prod: str, start, end) -> list[dict]:
    mapped: list[dict] = []
    inner_cut = end - timedelta(days=89)
    windows_inner = date_windows(max(start, inner_cut), end, 30)
    windows_before = date_windows(start, min(end, inner_cut - timedelta(days=1)), 30) if start < inner_cut else []
    demo = is_demo(ctx["env"])
    plans: list[tuple[str, list]] = []
    if windows_inner:
        plans.append(("VTTC0081R" if demo else "TTTC0081R", windows_inner))
    if windows_before:
        plans.append(("VTSC9215R" if demo else "CTSC9215R", windows_before))
    for tr_id, windows in plans:
        for a, b in windows:
            time.sleep(0.25)
            rows, _s = paged_get(
                path="/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
                tr_id=tr_id,
                query={
                    "CANO": cano,
                    "ACNT_PRDT_CD": prod,
                    "INQR_STRT_DT": fmt_yyyymmdd(a),
                    "INQR_END_DT": fmt_yyyymmdd(b),
                    "SLL_BUY_DVSN_CD": "00",
                    "PDNO": "",
                    "CCLD_DVSN": "01",
                    "INQR_DVSN": "01",
                    "INQR_DVSN_3": "00",
                    "ORD_GNO_BRNO": "",
                    "ODNO": "",
                    "INQR_DVSN_1": "",
                    "CTX_AREA_FK100": "",
                    "CTX_AREA_NK100": "",
                    "EXCG_ID_DVSN_CD": "ALL",
                },
                base=ctx["base"],
                appkey=ctx["appkey"],
                appsecret=ctx["appsecret"],
                token=ctx["token"],
                fk_key="CTX_AREA_FK100",
                nk_key="CTX_AREA_NK100",
            )
            mapped.extend(m for r in rows if (m := map_domestic_fill(r, cano=cano)))
    return mapped


def fetch_overseas_fills(ctx: dict, cano: str, prod: str, start, end) -> list[dict]:
    mapped: list[dict] = []
    tr_id = "VTTS3035R" if is_demo(ctx["env"]) else "TTTS3035R"
    for a, b in date_windows(start, end, 30):
        time.sleep(0.25)
        rows, _s = paged_get(
            path="/uapi/overseas-stock/v1/trading/inquire-ccnl",
            tr_id=tr_id,
            query={
                "CANO": cano,
                "ACNT_PRDT_CD": prod,
                "PDNO": "%",
                "ORD_STRT_DT": fmt_yyyymmdd(a),
                "ORD_END_DT": fmt_yyyymmdd(b),
                "SLL_BUY_DVSN": "00",
                "CCLD_NCCS_DVSN": "01",
                "OVRS_EXCG_CD": "%",
                "SORT_SQN": "DS",
                "ORD_DT": "",
                "ORD_GNO_BRNO": "",
                "ODNO": "",
                "CTX_AREA_NK200": "",
                "CTX_AREA_FK200": "",
            },
            base=ctx["base"],
            appkey=ctx["appkey"],
            appsecret=ctx["appsecret"],
            token=ctx["token"],
            fk_key="CTX_AREA_FK200",
            nk_key="CTX_AREA_NK200",
            output_key="output",
        )
        mapped.extend(m for r in rows if (m := map_overseas_fill(r, cano=cano)))
    return mapped


def fetch_domestic_dividends(ctx: dict, cano: str, prod: str, start, end) -> list[dict]:
    mapped: list[dict] = []
    seen: set[str] = set()
    right_codes = ("", "03")
    for a, b in date_windows(start, end, 90):
        for rght in right_codes:
            time.sleep(0.25)
            try:
                rows, _s = paged_get(
                    path="/uapi/domestic-stock/v1/trading/period-rights",
                    tr_id="CTRGA011R",
                    query={
                        "INQR_DVSN": "03",
                        "CANO": cano,
                        "ACNT_PRDT_CD": prod,
                        "INQR_STRT_DT": fmt_yyyymmdd(a),
                        "INQR_END_DT": fmt_yyyymmdd(b),
                        "CUST_RNCNO25": "",
                        "HMID": "",
                        "RGHT_TYPE_CD": rght,
                        "PDNO": "",
                        "PRDT_TYPE_CD": "",
                        "CTX_AREA_NK100": "",
                        "CTX_AREA_FK100": "",
                    },
                    base=ctx["base"],
                    appkey=ctx["appkey"],
                    appsecret=ctx["appsecret"],
                    token=ctx["token"],
                    fk_key="CTX_AREA_FK100",
                    nk_key="CTX_AREA_NK100",
                    output_key="output",
                )
            except Exception as exc:
                print(f"  domestic rights skip {a}:{b} rght={rght or '*'}: {exc}")
                continue
            for r in rows:
                m = map_domestic_dividend(r, cano=cano)
                if not m or m["external_id"] in seen:
                    continue
                seen.add(m["external_id"])
                mapped.append(m)
            if mapped and not rght:
                break
    return mapped


def _kis_settings_row() -> dict | None:
    try:
        rows = (
            supabase()
            .table("kis_api_settings")
            .select("app_key,app_secret,accounts,env")
            .eq("id", 1)
            .execute()
            .data
            or []
        )
    except Exception:
        return None
    return rows[0] if rows else None


def kis_credentials() -> tuple[str, str, str, list[tuple[str, str]]]:
    env_key = os.getenv("KIS_APP_KEY", "")
    env_secret = os.getenv("KIS_APP_SECRET", "")
    env_cano = os.getenv("KIS_CANO", "")
    env_accounts = os.getenv("KIS_ACCOUNTS", "")
    db = None
    if not env_key.strip() or not env_secret.strip() or not (env_cano.strip() or env_accounts.strip()):
        db = _kis_settings_row()
    return merge_credentials(
        env_key=env_key,
        env_secret=env_secret,
        env_env=os.getenv("KIS_ENV", ""),
        env_cano=env_cano,
        env_product=os.getenv("KIS_ACNT_PRDT_CD", "01"),
        env_accounts=env_accounts,
        db=db,
    )


def normalize_stored_dividend_tickers(c) -> int:
    rows = c.table("dividends").select("id,ticker").execute().data or []
    n = 0
    for row in rows:
        nxt = normalize_kr_ticker(row.get("ticker"))
        if not nxt or nxt == row.get("ticker"):
            continue
        c.table("dividends").update({"ticker": nxt}).eq("id", row["id"]).execute()
        n += 1
    return n


def run_sync(*, user_id: str | None = None, require_creds: bool = True) -> dict:
    appkey, appsecret, env, accounts = kis_credentials()
    if not appkey or not appsecret:
        msg = (
            "한투 앱키와 앱시크릿이 필요합니다. "
            "앱 기록하기 → 한투 동기화에 붙여 넣거나 KIS Developers에서 발급하세요."
        )
        if require_creds:
            raise RuntimeError(msg)
        print(msg)
        return {"ok": True, "skipped": True, "reason": "missing-keys"}
    if not accounts:
        msg = (
            "한투 계좌(예: 12345678-01)가 필요합니다. "
            "앱 기록하기 → 한투 동기화에 계좌를 저장하세요."
        )
        if require_creds:
            raise RuntimeError(msg)
        print(msg)
        return {"ok": True, "skipped": True, "reason": "missing-account"}

    ip = public_ip()
    print(f"Public IP (allow-list this in KIS Developers if IP lock is on): {ip}")

    c = supabase()
    try:
        fixed = normalize_stored_dividend_tickers(c)
        if fixed:
            print(f"  normalized {fixed} dividend ticker(s)")
    except Exception as exc:
        print(f"  dividend ticker normalize skip: {exc}")
    uid = user_id
    if not uid:
        users = c.table("users").select("id,email").eq("email", USER_EMAIL).execute().data or []
        if not users:
            raise RuntimeError(f"User {USER_EMAIL} not found — log in once first")
        uid = users[0]["id"]

    base = kis_base(env)
    token = issue_token(appkey, appsecret, base, db=c)
    print("Token ok")
    ctx = {
        "env": env,
        "base": base,
        "appkey": appkey,
        "appsecret": appsecret,
        "token": token,
    }
    start, end = lookback_range(TRADE_LOOKBACK_DAYS)

    fills: list[dict] = []
    dividends: list[dict] = []
    products: list[dict] = []
    account_ids: dict[str, str] = {}
    summary: list[dict] = []
    isa_seen = False

    def tag_rows(rows: list[dict], prod: str) -> list[dict]:
        out = []
        for row in rows:
            item = dict(row)
            item["product"] = prod
            out.append(item)
        return out

    for i, (cano, prod) in enumerate(accounts):
        if i:
            time.sleep(0.9)
        print(f"  account {cano}-{prod}", flush=True)
        kr_hold: list[dict] = []
        kr_cash = 0.0
        ov_cash = 0.0
        usd_cash = 0.0
        us_hold: list[dict] = []
        fund = 0.0
        note = ""
        try:
            kr_hold, kr_cash = fetch_domestic_balance(ctx, cano, prod)
        except Exception as exc:
            note = str(exc)
            print(f"  domestic balance skip: {exc}", flush=True)
        if prod == "21":
            try:
                ov = fetch_account_overview(ctx, cano, prod)
                if ov.get("ok"):
                    isa_seen = True
                    ov_cash = ov["cash"]
                    if not kr_hold and ov["nass"] > 0:
                        fund = ov["nass"]
                        kr_hold.append(
                            {
                                "ticker": ISA_FUND_TICKER,
                                "name": ISA_FUND_HOLDING_NAME,
                                "quantity": 1.0,
                                "avg_price": fund,
                                "currency": "KRW",
                                "last_price": fund,
                            }
                        )
                        note = note or "펀드는 종목 API가 없어 이 계좌 보유로 반영"
            except Exception as exc:
                print(f"  21 overview skip: {exc}", flush=True)
                note = note or str(exc)
        try:
            us_hold = fetch_overseas_balance(ctx, cano, prod)
        except Exception as exc:
            print(f"  overseas balance skip: {exc}")
        try:
            usd_cash = fetch_overseas_cash(ctx, cano, prod)
        except Exception as exc:
            print(f"  usd cash skip: {exc}")
        prod_fills: list[dict] = []
        prod_divs: list[dict] = []
        try:
            prod_fills.extend(tag_rows(fetch_domestic_fills(ctx, cano, prod, start, end), prod))
        except Exception as exc:
            print(f"  domestic fills skip: {exc}")
        try:
            prod_fills.extend(tag_rows(fetch_overseas_fills(ctx, cano, prod, start, end), prod))
        except Exception as exc:
            print(f"  overseas fills skip: {exc}")
        try:
            prod_divs.extend(tag_rows(fetch_domestic_dividends(ctx, cano, prod, start, end), prod))
        except Exception as exc:
            print(f"  domestic dividends skip: {exc}")
        try:
            estimated = estimate_holding_dividends(
                kr_hold,
                from_date=start.isoformat(),
                to_date=end.isoformat(),
                source="kis",
            )
            prod_divs = merge_estimated_dividends(prod_divs, tag_rows(estimated, prod))
        except Exception as exc:
            print(f"  yahoo dividend estimate skip: {exc}")
        fills.extend(prod_fills)
        dividends.extend(prod_divs)

        prod_holdings = kr_hold + us_hold
        by_ccy = holdings_by_currency(prod_holdings)
        cash_by = {"KRW": kr_cash + ov_cash, "USD": usd_cash}
        trade_ccy = {m["currency"] for m in prod_fills}
        div_ccy = {m["currency"] for m in prod_divs}
        for ccy in ("KRW", "USD"):
            rows = by_ccy.get(ccy) or []
            if not rows and cash_by[ccy] <= 0 and ccy not in trade_ccy and ccy not in div_ccy:
                continue
            aid = ensure_account(c, uid, ccy, prod)
            account_ids[f"{prod}:{ccy}"] = aid
            upsert_holdings(c, aid, rows)
            set_cash(c, aid, cash_by[ccy])
            set_product_account_memo(c, aid, prod)

        products.append(
            {
                "code": prod,
                "label": product_label(prod),
                "holdings": len(kr_hold) + len(us_hold),
                "cash": kr_cash + ov_cash,
                "fund": fund,
                "note": note,
            }
        )

    trades_by = insert_trades(c, user_id=uid, account_ids=account_ids, rows=fills) if account_ids else {}
    divs_by = insert_dividends(c, user_id=uid, account_ids=account_ids, rows=dividends) if account_ids else {}
    if isa_seen:
        try:
            delete_isa_other_asset(c, uid)
        except Exception as exc:
            print(f"  isa other_asset skip: {exc}")

    trade_n = sum(trades_by.values())
    div_n = sum(divs_by.values())
    for p in products:
        summary.append(
            {
                "currency": "KRW",
                "product": p["code"],
                "label": p["label"],
                "holdings": p["holdings"],
                "cash": p["cash"],
            }
        )
        print(
            f"  {INSTITUTION} {p['label']}: {p['holdings']} holdings, cash={p['cash']}"
            + (f" ({p['note']})" if p.get("note") else "")
        )

    print(f"Done. Synced {INSTITUTION}. 체결 {trade_n}건, 배당 {div_n}건")
    return {
        "ok": True,
        "institution": INSTITUTION,
        "accounts": summary,
        "products": products,
        "egress_ip": ip,
        "trades": trade_n,
        "dividends": div_n,
        "sync_revision": SYNC_REVISION,
    }


def main() -> None:
    skip = os.getenv("KIS_SKIP_IF_UNCONFIGURED", "").strip() in {"1", "true", "yes"}
    try:
        run_sync(require_creds=not skip)
    except Exception as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
    sys.exit(0)
