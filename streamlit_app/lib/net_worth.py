"""Net worth composition: invest + cash + deposits + other − debt."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd


def market_region(ticker: str | None, ccy: str | None) -> str:
    t = str(ticker or "").strip()
    if t.isdigit() and len(t) == 6:
        return "국내"
    if (ccy or "").upper() == "KRW":
        return "국내"
    return "해외"

OWNERSHIP_KO = {"joint": "공동", "mine": "정명", "spouse": "지수"}
ASSET_KIND_KO = {
    "real_estate": "부동산",
    "pension": "연금",
    "insurance": "보험",
    "crypto": "암호화폐",
    "other": "기타",
}
ASSET_KIND_KO_ALL = {
    **ASSET_KIND_KO,
    "deposit": "예적금",
}
DEPOSIT_KIND_KO = {
    "demand": "입출금",
    "time": "정기예금",
    "installment": "적금",
    "subscription": "청약",
    "cma": "CMA",
    "other": "기타",
}
ALLOC_CAT_KO = {
    "domestic": "국내주식",
    "overseas": "해외주식",
    "cash": "현금·예수금",
    "deposits": "예적금",
    "other": "기타자산",
}


def _safe_table(client, table: str, select: str = "*", **filters) -> list[dict]:
    try:
        q = client.table(table).select(select)
        for k, v in filters.items():
            q = q.eq(k, v)
        return q.execute().data or []
    except Exception:
        return []


def _to_krw(amount: float | None, ccy: str | None, usdkrw: float | None) -> float:
    if amount is None:
        return 0.0
    try:
        n = float(amount)
    except (TypeError, ValueError):
        return 0.0
    if (ccy or "KRW").upper() == "USD":
        return n * float(usdkrw) if usdkrw else 0.0
    return n


def load_other_assets(client) -> list[dict]:
    return _safe_table(client, "other_assets", "*")


def load_deposits(client) -> list[dict]:
    return _safe_table(client, "deposits", "*")


def deposit_balance(row: dict, as_of: str | None = None) -> float:
    prog = installment_progress(row, as_of)
    if prog is not None:
        return float(prog["value"])
    try:
        cur = float(row.get("current_value") or 0)
    except (TypeError, ValueError):
        cur = 0.0
    if cur > 0:
        return cur
    try:
        principal = float(row.get("principal") or 0)
    except (TypeError, ValueError):
        principal = 0.0
    if principal > 0:
        return principal
    try:
        return float(row.get("value_krw") or 0)
    except (TypeError, ValueError):
        return 0.0


def _iso_ymd(value) -> str:
    s = str(value or "").strip()
    return s[:10] if len(s) >= 10 else ""


def _calendar_months_between(start: str, end: str) -> int:
    try:
        y1, m1, d1 = (int(x) for x in start.split("-")[:3])
        y2, m2, d2 = (int(x) for x in end.split("-")[:3])
    except (TypeError, ValueError):
        return 0
    months = (y2 - y1) * 12 + (m2 - m1)
    if d2 < d1:
        months -= 1
    return max(0, months)


def installment_progress(row: dict, as_of: str | None = None) -> dict | None:
    """적금/청약 월납 단리. 없으면 None.

    current_value > 0 이면 그 금액을 balance_as_of 기준으로 쓰고 이후 회차만 가산.
    """
    kind = str(row.get("deposit_kind") or "")
    if kind not in ("installment", "subscription"):
        return None
    try:
        monthly = float(row.get("monthly_amount") or 0)
    except (TypeError, ValueError):
        monthly = 0.0
    if monthly <= 0:
        return None
    start = _iso_ymd(row.get("start_date"))
    if len(start) != 10:
        return None
    maturity = _iso_ymd(row.get("maturity_date"))
    today = as_of or date.today().isoformat()
    if len(maturity) == 10:
        total = max(1, _calendar_months_between(start, maturity))
    else:
        total = 0
    cap = total if total > 0 else 1200

    def _made(asof: str) -> int:
        if asof < start:
            return 0
        until = maturity if len(maturity) == 10 and maturity < asof else asof
        return min(cap, _calendar_months_between(start, until) + 1)

    made = _made(today)
    try:
        rate = float(row.get("interest_rate") or 0) / 100.0
    except (TypeError, ValueError):
        rate = 0.0
    formula_interest = round(monthly * (rate / 12.0) * made * max(made - 1, 0) / 2.0)
    n = total if total > 0 else made
    formula_maturity_interest = round(monthly * rate * n * (n + 1) / 24.0)
    principal = monthly * made
    remaining = max(0, n - made)
    try:
        seed = float(row.get("current_value") or 0)
    except (TypeError, ValueError):
        seed = 0.0
    seed_on = _iso_ymd(row.get("balance_as_of")) or today
    use_seed = seed > 0 and today >= seed_on
    extra = 0
    value = principal + formula_interest
    interest = formula_interest
    if use_seed:
        extra = max(0, made - _made(seed_on))
        extra_interest = round(
            monthly * (rate / 12.0) * extra * max(extra - 1, 0) / 2.0
        )
        value = seed + monthly * extra + extra_interest
        interest = extra_interest
        principal = seed + monthly * extra
    remaining_interest = round(
        monthly * (rate / 12.0) * remaining * max(remaining - 1, 0) / 2.0
    )
    if use_seed:
        maturity_value = value + monthly * remaining + remaining_interest
        maturity_interest = remaining_interest
        maturity_principal = seed + monthly * remaining
    else:
        maturity_value = monthly * n + formula_maturity_interest
        maturity_interest = formula_maturity_interest
        maturity_principal = monthly * n
    return {
        "monthly": monthly,
        "payments_made": made,
        "payments_total": n,
        "principal": principal,
        "interest": interest,
        "value": value,
        "maturity_principal": maturity_principal,
        "maturity_interest": maturity_interest,
        "maturity_value": maturity_value,
        "seeded": use_seed,
        "seed_value": seed if use_seed else 0.0,
        "extra_payments": extra,
    }


def load_allocation_targets(client) -> dict[str, float]:
    rows = _safe_table(client, "allocation_targets", "category,target_pct")
    out = {c: 0.0 for c in ("domestic", "overseas", "cash", "deposits", "other")}
    for r in rows:
        cat = str(r.get("category") or "")
        if cat in out:
            try:
                out[cat] = float(r.get("target_pct") or 0)
            except (TypeError, ValueError):
                out[cat] = 0.0
    return out


def load_accounts_enriched(client) -> list[dict]:
    try:
        rows = (
            client.table("accounts")
            .select("id,institution,account_type,currency,ownership,cash_balance")
            .execute()
            .data
            or []
        )
        for a in rows:
            a.setdefault("ownership", "joint")
            a.setdefault("cash_balance", 0)
        return rows
    except Exception:
        lean = _safe_table(client, "accounts", "id,institution,account_type,currency")
        for a in lean:
            a.setdefault("ownership", "joint")
            a.setdefault("cash_balance", 0)
        return lean


def compute_net_worth(
    live_rows: list[dict],
    *,
    accounts: list[dict],
    other_assets: list[dict],
    total_debt: float,
    usdkrw: float | None,
    account_ids: list[str] | None = None,
    ownership: str | None = None,
    deposits: list[dict] | None = None,
) -> dict[str, Any]:
    """Return NW breakdown in KRW.

    invest = brokerage holdings market value
    cash = account cash_balance (증권 예수금) + bank holdings
    deposits = 예적금 평가액 (table + leftover other_assets.deposit)
    other = other_assets.value_krw excluding deposit
    debt = total_debt (caller may already filter)
    net = invest + cash + deposits + other - debt
    """
    allow = {str(a) for a in account_ids} if account_ids is not None else None
    own = ownership if ownership in ("joint", "mine", "spouse") else None

    acct_map = {str(a["id"]): a for a in accounts}

    def _acct_ok(aid: str | None) -> bool:
        if allow is not None and str(aid or "") not in allow:
            return False
        if own is None:
            return True
        a = acct_map.get(str(aid or ""))
        return (a or {}).get("ownership", "joint") == own

    invest = 0.0
    domestic = 0.0
    overseas = 0.0
    bank_holdings_cash = 0.0

    for r in live_rows:
        aid = str(r.get("account_id") or "")
        if allow is not None and aid not in allow:
            continue
        a = acct_map.get(aid) or {}
        if own is not None and a.get("ownership", "joint") != own:
            continue
        v = _to_krw(r.get("value"), r.get("ccy"), usdkrw)
        atype = a.get("account_type") or "brokerage"
        if atype == "bank":
            bank_holdings_cash += v
            continue
        if atype == "loan":
            continue
        invest += v
        region = market_region(r.get("ticker"), r.get("ccy"))
        if region == "국내":
            domestic += v
        else:
            overseas += v

    cash = bank_holdings_cash
    for a in accounts:
        aid = str(a.get("id") or "")
        if allow is not None and aid not in allow:
            continue
        if own is not None and a.get("ownership", "joint") != own:
            continue
        cash += _to_krw(a.get("cash_balance"), a.get("currency"), usdkrw)

    other = 0.0
    other_rows: list[dict] = []
    deposits_sum = 0.0
    deposit_rows: list[dict] = []
    for o in other_assets:
        if own is not None and o.get("ownership", "joint") != own:
            continue
        if allow is not None:
            continue
        try:
            val = float(o.get("value_krw") or 0)
        except (TypeError, ValueError):
            val = 0.0
        if str(o.get("asset_kind") or "") == "deposit":
            deposits_sum += val
            deposit_rows.append(o)
            continue
        other += val
        other_rows.append(o)

    if allow is None:
        for d in deposits or []:
            if own is not None and d.get("ownership", "joint") != own:
                continue
            deposits_sum += deposit_balance(d)
            deposit_rows.append(d)

    # When account-filtered, omit household other assets / deposits from NW
    if allow is not None:
        other = 0.0
        other_rows = []
        deposits_sum = 0.0
        deposit_rows = []

    debt = float(total_debt or 0)
    if allow is not None:
        # caller usually passes 0 for filtered account debt already
        pass

    gross = invest + cash + deposits_sum + other
    net = gross - debt
    return {
        "invest": invest,
        "cash": cash,
        "deposits": deposits_sum,
        "other": other,
        "debt": debt,
        "gross": gross,
        "net": net,
        "domestic": domestic,
        "overseas": overseas,
        "other_rows": other_rows,
        "deposit_rows": deposit_rows,
        "cash_ratio": (cash / gross) if gross > 0 else 0.0,
    }


def allocation_actual(nw: dict[str, Any]) -> dict[str, float]:
    """Actual % of gross assets by category."""
    gross = float(nw.get("gross") or 0)
    if gross <= 0:
        return {c: 0.0 for c in ("domestic", "overseas", "cash", "deposits", "other")}
    return {
        "domestic": 100.0 * float(nw.get("domestic") or 0) / gross,
        "overseas": 100.0 * float(nw.get("overseas") or 0) / gross,
        "cash": 100.0 * float(nw.get("cash") or 0) / gross,
        "deposits": 100.0 * float(nw.get("deposits") or 0) / gross,
        "other": 100.0 * float(nw.get("other") or 0) / gross,
    }


def allocation_drift(
    actual: dict[str, float], targets: dict[str, float]
) -> list[dict[str, Any]]:
    rows = []
    for cat in ("domestic", "overseas", "cash", "deposits", "other"):
        a = float(actual.get(cat) or 0)
        t = float(targets.get(cat) or 0)
        rows.append(
            {
                "category": cat,
                "label": ALLOC_CAT_KO.get(cat, cat),
                "actual_pct": a,
                "target_pct": t,
                "drift_pct": a - t,
            }
        )
    return rows


def monthly_summary_stats(
    client,
    *,
    live_net: float | None,
    account_ids: list[str] | None = None,
) -> dict[str, Any]:
    """This-month NW change vs prior month-end snapshot + simple tallies."""
    today = date.today()
    month_start = today.replace(day=1)
    prev_end = month_start - timedelta(days=1)

    out: dict[str, Any] = {
        "month_start": month_start.isoformat(),
        "nw_start": None,
        "nw_now": live_net,
        "nw_change": None,
        "nw_change_pct": None,
    }

    try:
        snaps = (
            client.table("daily_snapshots")
            .select("snapshot_date,net_assets")
            .gte("snapshot_date", (prev_end - timedelta(days=5)).isoformat())
            .lte("snapshot_date", today.isoformat())
            .order("snapshot_date")
            .execute()
            .data
            or []
        )
    except Exception:
        snaps = []

    if snaps:
        # Prefer snapshot on/before month start
        prior = [
            s
            for s in snaps
            if str(s.get("snapshot_date") or "") <= month_start.isoformat()
        ]
        if prior:
            try:
                out["nw_start"] = float(prior[-1]["net_assets"])
            except (TypeError, ValueError, KeyError):
                out["nw_start"] = None

    if out["nw_start"] is not None and live_net is not None:
        out["nw_change"] = float(live_net) - float(out["nw_start"])
        if abs(float(out["nw_start"])) > 1:
            out["nw_change_pct"] = 100.0 * out["nw_change"] / float(out["nw_start"])

    # Realized-ish: sum v_total_realized_pnl for month if available
    try:
        since = month_start.isoformat()
        q = (
            client.table("v_total_realized_pnl")
            .select("event_date,pnl_krw,pnl,currency")
            .gte("event_date", since)
        )
        rows = q.execute().data or []
        if account_ids is not None:
            # view may not have account_id — skip filter
            pass
        total = 0.0
        for r in rows:
            v = r.get("pnl_krw")
            if v is None:
                v = r.get("pnl")
            try:
                total += float(v or 0)
            except (TypeError, ValueError):
                pass
        out["realized_month"] = total
    except Exception:
        out["realized_month"] = None

    return out


def debts_due_soon(client, *, within_days: int = 45) -> list[dict]:
    today = date.today()
    end = today + timedelta(days=within_days)
    debts = _safe_table(client, "debts", "id,lender,principal,interest_rate,due_date,ownership")
    due = []
    for d in debts:
        raw = d.get("due_date")
        if not raw:
            continue
        try:
            dd = date.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
        if today <= dd <= end:
            due.append({**d, "_due": dd, "_days": (dd - today).days})
    due.sort(key=lambda x: x["_due"])
    return due
