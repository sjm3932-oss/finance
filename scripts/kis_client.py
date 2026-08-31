"""Korea Investment (한투) Open API helpers.

Inquiry only — does not place orders.

Docs: https://apiportal.koreainvestment.com
Real: https://openapi.koreainvestment.com:9443
Paper: https://openapivts.koreainvestment.com:29443
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Iterable
from zoneinfo import ZoneInfo

KIS_REAL_BASE = "https://openapi.koreainvestment.com:9443"
KIS_DEMO_BASE = "https://openapivts.koreainvestment.com:29443"
INSTITUTION = "한국투자증권"
ACCOUNT_TYPE = "brokerage"
KST = ZoneInfo("Asia/Seoul")

DIVIDEND_NAME_HINTS = ("배당", "분배")
DIVIDEND_RIGHT_CODES = {"03", "04", "17", "18"}  # 현금배당 / 주식배당 / ETF분배 등


def kis_base(env: str) -> str:
    return KIS_DEMO_BASE if str(env).lower() in {"demo", "paper", "vts"} else KIS_REAL_BASE


def is_demo(env: str) -> bool:
    return str(env).lower() in {"demo", "paper", "vts"}


def to_number(raw: Any) -> float:
    if raw is None or raw == "":
        return 0.0
    n = float(str(raw).replace(",", "").strip())
    if not (n == n):  # NaN
        return 0.0
    return n


def pick(row: dict[str, Any], *keys: str, default: Any = "") -> Any:
    if not isinstance(row, dict):
        return default
    lower = {str(k).lower(): v for k, v in row.items()}
    for key in keys:
        val = row.get(key)
        if val not in (None, ""):
            return val
        val = lower.get(key.lower())
        if val not in (None, ""):
            return val
    return default


def yyyymmdd(raw: Any) -> str | None:
    s = str(raw or "").strip().replace("-", "")
    if len(s) >= 8 and s[:8].isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    if len(str(raw or "")) >= 10 and str(raw)[4] == "-" and str(raw)[7] == "-":
        return str(raw)[:10]
    return None


def normalize_kr_ticker(raw: Any) -> str:
    t = str(raw or "").strip().upper()
    if t.startswith("A") and t[1:].isdigit():
        t = t[1:]
    if t.endswith(".KS") or t.endswith(".KQ"):
        t = t[:-3]
    if t.isdigit() and len(t) <= 6:
        return t.zfill(6)
    return t


def normalize_us_ticker(raw: Any) -> str:
    t = str(raw or "").strip().upper()
    if t.startswith("US") and len(t) > 6 and not t[2:].isdigit():
        t = t[2:]
    return t


def parse_account_spec(raw: str) -> tuple[str, str] | None:
    """Parse '12345678-01' / '1234567801' / '12345678' into (CANO, product)."""
    s = str(raw or "").strip().replace(" ", "")
    if not s:
        return None
    if "-" in s:
        left, right = s.split("-", 1)
        cano = "".join(ch for ch in left if ch.isdigit())
        prod = "".join(ch for ch in right if ch.isdigit())[:2]
        if len(cano) >= 8 and prod:
            return cano[:8], prod.zfill(2)
        return None
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) >= 10:
        return digits[:8], digits[8:10]
    if len(digits) == 8:
        return digits, "01"
    return None


def parse_accounts(cano: str, product: str, accounts_csv: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    chunks = [p.strip() for p in str(accounts_csv or "").split(",") if p.strip()]
    if cano.strip():
        spec = parse_account_spec(
            f"{cano.strip()}-{product.strip() or '01'}" if "-" not in cano else cano
        )
        if spec:
            chunks.insert(0, f"{spec[0]}-{spec[1]}")
    for chunk in chunks:
        spec = parse_account_spec(chunk)
        if spec and spec not in seen:
            seen.add(spec)
            out.append(spec)
    return out


def merge_credentials(
    *,
    env_key: str,
    env_secret: str,
    env_env: str,
    env_cano: str,
    env_product: str,
    env_accounts: str,
    db: dict[str, Any] | None,
) -> tuple[str, str, str, list[tuple[str, str]]]:
    """Env wins when set; otherwise fall back to kis_api_settings row."""
    appkey = str(env_key or "").strip()
    appsecret = str(env_secret or "").strip()
    env = str(env_env or "").strip() or "real"
    cano = str(env_cano or "").strip()
    product = str(env_product or "").strip() or "01"
    accounts_csv = str(env_accounts or "").strip()
    if db:
        appkey = appkey or str(db.get("app_key") or "").strip()
        appsecret = appsecret or str(db.get("app_secret") or "").strip()
        if not str(env_env or "").strip():
            env = str(db.get("env") or "").strip() or env
        if not cano and not accounts_csv:
            accounts_csv = str(db.get("accounts") or "").strip()
    accounts = parse_accounts(cano, product, accounts_csv)
    return appkey, appsecret, env, accounts


def output_rows(payload: Any, *keys: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    blob: Any = None
    for key in keys:
        if key in payload:
            blob = payload[key]
            break
        for actual, val in payload.items():
            if str(actual).lower() == key.lower():
                blob = val
                break
        if blob is not None:
            break
    if blob is None:
        return []
    if isinstance(blob, list):
        return [x for x in blob if isinstance(x, dict)]
    if isinstance(blob, dict):
        return [blob]
    return []


def map_domestic_holding(item: dict[str, Any]) -> dict[str, Any] | None:
    ticker = normalize_kr_ticker(pick(item, "pdno", "shtn_pdno"))
    if not ticker:
        return None
    qty = to_number(pick(item, "hldg_qty", "ord_psbl_qty"))
    if qty <= 0:
        return None
    return {
        "ticker": ticker,
        "name": str(pick(item, "prdt_name", "item_name") or ticker).strip() or ticker,
        "quantity": qty,
        "avg_price": to_number(pick(item, "pchs_avg_pric", "pchs_avg_unpr")),
        "currency": "KRW",
        "last_price": to_number(pick(item, "prpr", "now_pric2")),
    }


def map_overseas_holding(item: dict[str, Any]) -> dict[str, Any] | None:
    ticker = normalize_us_ticker(pick(item, "ovrs_pdno", "pdno", "item_cd"))
    if not ticker:
        return None
    qty = to_number(pick(item, "ovrs_cblc_qty", "hldg_qty", "cblc_qty13"))
    if qty <= 0:
        return None
    currency = str(pick(item, "tr_crcy_cd", "crcy_cd") or "USD").upper()
    if currency not in {"USD", "HKD", "JPY", "CNY", "EUR"}:
        currency = "USD"
    if currency != "USD":
        # Household ledger currently splits KRW / USD like Toss.
        currency = "USD"
    return {
        "ticker": ticker,
        "name": str(pick(item, "ovrs_item_name", "prdt_name", "item_name") or ticker).strip()
        or ticker,
        "quantity": qty,
        "avg_price": to_number(pick(item, "pchs_avg_pric", "avg_unpr", "pchs_avg_unpr3")),
        "currency": currency,
        "last_price": to_number(pick(item, "now_pric2", "ovrs_now_pric1", "prpr")),
    }


def merge_holdings(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_ticker: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["ticker"], row["currency"])
        prev = by_ticker.get(key)
        if not prev:
            by_ticker[key] = dict(row)
            continue
        q1 = to_number(prev["quantity"])
        q2 = to_number(row["quantity"])
        qty = q1 + q2
        if qty > 0:
            prev["avg_price"] = (
                to_number(prev["avg_price"]) * q1 + to_number(row["avg_price"]) * q2
            ) / qty
        prev["quantity"] = qty
        if row.get("last_price"):
            prev["last_price"] = row["last_price"]
        if row.get("name") and not prev.get("name"):
            prev["name"] = row["name"]
    return list(by_ticker.values())


def holdings_by_currency(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"KRW": [], "USD": []}
    for row in merge_holdings(rows):
        bucket = row["currency"] if row["currency"] in out else "KRW"
        out[bucket].append(row)
    return out


def domestic_cash(summary: dict[str, Any] | None) -> float:
    if not summary:
        return 0.0
    return to_number(
        pick(summary, "dnca_tot_amt", "nxdy_excc_amt", "prvs_rcdl_excc_amt", "nass_amt")
    )


def overseas_cash(rows: list[dict[str, Any]], currency: str = "USD") -> float:
    total = 0.0
    found = False
    for row in rows:
        ccy = str(pick(row, "crcy_cd", "tr_crcy_cd") or "").upper()
        if ccy and ccy != currency:
            continue
        amt = to_number(
            pick(
                row,
                "frcr_dncl_amt_2",
                "frcr_dncl_amt",
                "dncl_amt",
                "frcr_cblc_amt",
                "cblc_amt",
                "frcr_evlu_amt2",
            )
        )
        if amt or ccy == currency:
            found = True
            total += amt
    if found:
        return total
    if len(rows) == 1:
        return to_number(
            pick(
                rows[0],
                "frcr_dncl_amt_2",
                "frcr_dncl_amt",
                "dncl_amt",
                "frcr_cblc_amt",
            )
        )
    return 0.0


def _trade_type(code: Any, name: Any) -> str | None:
    raw = str(code or "").strip()
    label = str(name or "")
    if raw in {"02", "2", "BUY"} or "매수" in label:
        return "buy"
    if raw in {"01", "1", "SELL"} or "매도" in label:
        return "sell"
    return None


def map_domestic_fill(item: dict[str, Any], *, cano: str) -> dict[str, Any] | None:
    qty = to_number(pick(item, "tot_ccld_qty", "ccld_qty", "ft_ccld_qty"))
    if qty <= 0:
        return None
    price = to_number(pick(item, "avg_prvs", "ccld_avg_unpr", "avg_ccld_unpr", "ccld_unpr"))
    if price <= 0:
        return None
    trade_type = _trade_type(
        pick(item, "sll_buy_dvsn_cd", "sll_buy_dvsn"),
        pick(item, "sll_buy_dvsn_name", "trad_dvsn_name"),
    )
    if not trade_type:
        return None
    odno = str(pick(item, "odno", "ord_no") or "").strip()
    if not odno:
        return None
    ticker = normalize_kr_ticker(pick(item, "pdno", "shtn_pdno"))
    if not ticker:
        return None
    trade_date = yyyymmdd(pick(item, "ord_dt", "ord_gno_dt", "ccld_dt"))
    if not trade_date:
        return None
    fee = to_number(pick(item, "tot_tr_cost", "cmsn_amt", "tr_tax")) + to_number(
        pick(item, "tr_tax", "trde_tax")
    )
    # tot_tr_cost may already include tax; if both set, prefer tot_tr_cost only.
    if to_number(pick(item, "tot_tr_cost")):
        fee = to_number(pick(item, "tot_tr_cost"))
    return {
        "external_id": f"kis:kr:{cano}:{trade_date}:{odno}",
        "ticker": ticker,
        "trade_type": trade_type,
        "price": price,
        "quantity": qty,
        "fee": fee,
        "currency": "KRW",
        "trade_date": trade_date,
        "reason": "한투 체결",
    }


def map_overseas_fill(item: dict[str, Any], *, cano: str) -> dict[str, Any] | None:
    qty = to_number(pick(item, "ft_ccld_qty", "ccld_qty", "tot_ccld_qty"))
    if qty <= 0:
        return None
    price = to_number(
        pick(item, "ft_ccld_unpr3", "ft_ccld_unpr", "avg_prvs", "ccld_unpr")
    )
    if price <= 0:
        return None
    trade_type = _trade_type(
        pick(item, "sll_buy_dvsn_cd", "sll_buy_dvsn"),
        pick(item, "sll_buy_dvsn_name", "trad_dvsn_name"),
    )
    if not trade_type:
        return None
    odno = str(pick(item, "odno", "ord_no") or "").strip()
    if not odno:
        return None
    ticker = normalize_us_ticker(pick(item, "pdno", "ovrs_pdno"))
    if not ticker:
        return None
    trade_date = yyyymmdd(pick(item, "ord_dt", "ccld_dt", "trad_dt"))
    if not trade_date:
        return None
    fee = to_number(pick(item, "tr_cmsn", "cmsn_amt", "ovrs_cmsn"))
    currency = str(pick(item, "tr_crcy_cd", "crcy_cd") or "USD").upper()
    if currency != "USD":
        currency = "USD"
    return {
        "external_id": f"kis:us:{cano}:{trade_date}:{odno}",
        "ticker": ticker,
        "trade_type": trade_type,
        "price": price,
        "quantity": qty,
        "fee": fee,
        "currency": currency,
        "trade_date": trade_date,
        "reason": "한투 체결",
    }


def _looks_like_dividend(code: Any, *names: Any) -> bool:
    raw = str(code or "").strip()
    if raw in DIVIDEND_RIGHT_CODES:
        return True
    blob = " ".join(str(n or "") for n in names)
    return any(hint in blob for hint in DIVIDEND_NAME_HINTS)


def map_domestic_dividend(item: dict[str, Any], *, cano: str) -> dict[str, Any] | None:
    name_bits = (
        pick(item, "rght_type_name", "rght_type_cd_name"),
        pick(item, "prdt_name"),
        pick(item, "rght_type_cd"),
    )
    if not _looks_like_dividend(pick(item, "rght_type_cd"), *name_bits):
        return None
    amount = to_number(
        pick(item, "last_alct_amt", "alct_amt", "stck_dvdn_unpr", "rfus_amt")
    )
    tax = to_number(pick(item, "intt_tax", "tax_amt", "stlm_tax"))
    if amount > 0 and tax > 0 and tax < amount:
        amount = amount - tax
    if amount <= 0:
        return None
    ticker = normalize_kr_ticker(pick(item, "pdno", "shtn_pdno"))
    if not ticker:
        return None
    pay_date = yyyymmdd(
        pick(item, "pay_dt", "alct_dt", "rght_offr_end_dt", "bass_dt", "stnd_dt")
    )
    if not pay_date:
        return None
    return {
        "external_id": f"kis:div:kr:{cano}:{pay_date}:{ticker}:{amount:.4f}",
        "ticker": ticker,
        "name": str(pick(item, "prdt_name") or ticker).strip() or ticker,
        "pay_date": pay_date,
        "amount": amount,
        "currency": "KRW",
        "memo": str(pick(item, "rght_type_name") or "한투 배당").strip() or "한투 배당",
    }


def map_overseas_dividend(item: dict[str, Any], *, cano: str) -> dict[str, Any] | None:
    name_bits = (
        pick(item, "sll_buy_dvsn_name", "trad_dvsn_name", "tr_type_name", "dvsn_name"),
        pick(item, "prdt_name", "ovrs_item_name"),
    )
    if not _looks_like_dividend(pick(item, "sll_buy_dvsn_cd", "tr_type_cd"), *name_bits):
        return None
    amount = abs(
        to_number(
            pick(
                item,
                "tr_amt",
                "ccld_amt",
                "ft_ccld_amt3",
                "frcr_tr_amt",
                "alct_amt",
            )
        )
    )
    if amount <= 0:
        return None
    ticker = normalize_us_ticker(pick(item, "pdno", "ovrs_pdno"))
    if not ticker:
        return None
    pay_date = yyyymmdd(pick(item, "trad_dt", "erlm_dt", "ccld_dt", "stlm_dt"))
    if not pay_date:
        return None
    currency = str(pick(item, "tr_crcy_cd", "crcy_cd") or "USD").upper()
    if currency != "USD":
        currency = "USD"
    return {
        "external_id": f"kis:div:us:{cano}:{pay_date}:{ticker}:{amount:.4f}",
        "ticker": ticker,
        "name": str(pick(item, "prdt_name", "ovrs_item_name") or ticker).strip() or ticker,
        "pay_date": pay_date,
        "amount": amount,
        "currency": currency,
        "memo": str(pick(item, "sll_buy_dvsn_name", "trad_dvsn_name") or "한투 배당").strip()
        or "한투 배당",
    }


def date_windows(start: date, end: date, days: int) -> list[tuple[date, date]]:
    if days < 1:
        days = 1
    if start > end:
        return []
    out: list[tuple[date, date]] = []
    cur = start
    while cur <= end:
        nxt = min(cur + timedelta(days=days - 1), end)
        out.append((cur, nxt))
        cur = nxt + timedelta(days=1)
    return out


def fmt_yyyymmdd(d: date) -> str:
    return d.strftime("%Y%m%d")


def kst_today() -> date:
    return datetime.now(KST).date()


def lookback_range(days: int) -> tuple[date, date]:
    end = kst_today()
    start = end - timedelta(days=max(1, days))
    return start, end


def local_account_key(currency: str) -> tuple[str, str, str]:
    return (INSTITUTION, ACCOUNT_TYPE, currency)


def humanize_kis_error(status: int, payload: Any) -> str:
    code = ""
    message = ""
    if isinstance(payload, dict):
        code = str(payload.get("msg_cd") or payload.get("error_code") or "")
        message = str(payload.get("msg1") or payload.get("msg") or payload.get("error") or "")
        err = payload.get("error")
        if isinstance(err, dict):
            code = code or str(err.get("code") or "")
            message = message or str(err.get("message") or "")
    if status == 403 or code in {"EGW00201", "EGW00204"}:
        return (
            "한투 Open API가 이 IP를 막았습니다. KIS Developers → 앱키 관리에서 "
            "현재 공인 IP를 허용했는지 확인하세요."
        )
    if status == 401 or code in {"EGW00121", "EGW00123", "EGW00002"}:
        return "한투 인증이 실패했습니다. 앱키와 앱시크릿을 확인하세요."
    if code == "EGW00133":
        return "한투 접근토큰이 이미 발급되어 있습니다. 잠시 후 다시 시도하세요."
    if status == 429:
        return "한투 API 호출 한도를 넘었습니다. 잠시 후 다시 시도하세요."
    if message:
        return message if "한투" in message else f"한투 API: {message}"
    if code:
        return f"한투 API 오류 ({code})"
    return f"한투 API HTTP {status}"
