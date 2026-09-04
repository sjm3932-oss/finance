#!/usr/bin/env python3
"""Clear dummy/demo transactional data without re-seeding.

Keeps Auth + public.users + allowed_emails + market_prices + chat logs,
and any real accounts listed in KEEP_INSTITUTIONS (한국투자증권).

Removes seed dummy institutions (토스증권 / 키움증권 / 카카오뱅크),
their ledger rows, dummy debts, and dummy net-worth snapshots.

Usage:
  cd /workspace && python3 scripts/clear_dummy_data.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

USER_EMAIL = os.getenv("CLEAR_USER_EMAIL", "sjm3932@gmail.com")
KEEP_INSTITUTIONS = {
    inst.strip()
    for inst in os.getenv("KEEP_INSTITUTIONS", "한국투자증권").split(",")
    if inst.strip()
}
DUMMY_INSTITUTIONS = {"토스증권", "키움증권", "카카오뱅크"}


def client():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def wipe_eq(c, table: str, col: str, value: str) -> None:
    try:
        c.table(table).delete().eq(col, value).execute()
        print(f"  cleared {table} where {col}={value[:8]}…")
    except Exception as exc:
        print(f"  skip {table}: {exc}")


def wipe_by_user(c, table: str, user_id: str) -> None:
    try:
        c.table(table).delete().eq("user_id", user_id).execute()
        print(f"  cleared {table} for user")
    except Exception as exc:
        print(f"  skip {table}: {exc}")


def wipe_all(c, table: str, col: str = "id") -> None:
    try:
        c.table(table).delete().neq(col, "00000000-0000-0000-0000-000000000000").execute()
        print(f"  cleared {table}")
    except Exception as exc:
        print(f"  skip {table}: {exc}")


def clear_ocr_storage(c, user_id: str) -> None:
    try:
        files = c.storage.from_("ocr-screenshots").list(user_id) or []
        paths = [f"{user_id}/{f['name']}" for f in files if f.get("name")]
        if paths:
            c.storage.from_("ocr-screenshots").remove(paths)
            print(f"  removed {len(paths)} OCR storage objects")
        else:
            print("  OCR storage empty")
    except Exception as exc:
        print(f"  OCR storage skip: {exc}")


def main() -> None:
    c = client()
    users = c.table("users").select("*").eq("email", USER_EMAIL).execute().data or []
    if not users:
        raise SystemExit(f"User {USER_EMAIL} not found")
    uid = users[0]["id"]
    print(f"Clearing dummy data for {USER_EMAIL} ({uid})")
    print(f"  keep institutions: {sorted(KEEP_INSTITUTIONS)}")

    clear_ocr_storage(c, uid)
    wipe_all(c, "ocr_staging")

    debts = c.table("debts").select("id,memo").eq("user_id", uid).execute().data or []
    dummy_debts = [d for d in debts if "더미" in (d.get("memo") or "")]
    if not dummy_debts and debts:
        print("  no debt memo marked 더미 — leaving debts in place")
    for d in dummy_debts:
        c.table("debt_transactions").delete().eq("debt_id", d["id"]).execute()
        try:
            c.table("debt_rate_history").delete().eq("debt_id", d["id"]).execute()
        except Exception:
            pass
        c.table("debts").delete().eq("id", d["id"]).execute()
        print(f"  cleared dummy debt {d['id']}")

    wipe_by_user(c, "other_assets", uid)
    wipe_by_user(c, "wealth_alert_events", uid)

    accts = c.table("accounts").select("id,institution").eq("user_id", uid).execute().data or []
    keep, dummy, unknown = [], [], []
    for a in accts:
        inst = a.get("institution") or ""
        if inst in KEEP_INSTITUTIONS:
            keep.append(a)
        elif inst in DUMMY_INSTITUTIONS:
            dummy.append(a)
        else:
            unknown.append(a)
    if unknown:
        print("  unknown institutions (left in place):")
        for a in unknown:
            print(f"    {a['institution']} {a['id']}")

    keep_ids = {a["id"] for a in keep}

    # User-scoped ledger rows that belong to dummy accounts only.
    # Dividends / cash_flows / tax_records from the seed are all on dummy accounts.
    for a in dummy:
        aid = a["id"]
        inst = a["institution"]
        print(f"  wiping dummy account {inst} ({aid})")
        wipe_eq(c, "trades", "account_id", aid)
        wipe_eq(c, "holdings", "account_id", aid)
        wipe_eq(c, "dividends", "account_id", aid)
        wipe_eq(c, "cash_flows", "account_id", aid)
        wipe_eq(c, "holding_daily_snapshots", "account_id", aid)
        c.table("accounts").delete().eq("id", aid).execute()
        print(f"  deleted account {inst}")

    # Seed tax row is dummy-only (no real trades on kept accounts).
    tax = c.table("tax_records").select("id,tax_year,cum_capital_gain").eq("user_id", uid).execute().data or []
    for row in tax:
        c.table("tax_records").delete().eq("id", row["id"]).execute()
        print(f"  cleared dummy tax_records {row['id']}")

    try:
        c.table("daily_snapshots").delete().gte("snapshot_date", "2000-01-01").execute()
        print("  cleared daily_snapshots (dummy net-worth history)")
    except Exception as exc:
        print(f"  daily_snapshots skip: {exc}")

    leftover = c.table("accounts").select("id,institution,account_type,currency").eq("user_id", uid).execute().data or []
    print("Remaining accounts:")
    for a in leftover:
        print(f"  {a['institution']} ({a['account_type']}/{a['currency']}) {a['id']}")
    if keep_ids and not any(a["id"] in keep_ids for a in leftover):
        raise SystemExit("ERROR: kept institution account is missing after clear")
    if not leftover:
        print("  (none)")

    print("Done. Kept 한국투자증권. Do NOT re-run scripts/seed_dummy_data.py.")


if __name__ == "__main__":
    main()
    sys.exit(0)
