#!/usr/bin/env python3
"""Clear dummy/demo transactional data without re-seeding.

Keeps Auth + public.users. Removes accounts, holdings, trades, debts,
other_assets, snapshots, OCR staging, etc.

Usage:
  cd /workspace && .venv/bin/python scripts/clear_dummy_data.py
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


def client():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


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
    except Exception as exc:
        print(f"  OCR storage skip: {exc}")


def main() -> None:
    c = client()
    users = c.table("users").select("*").eq("email", USER_EMAIL).execute().data or []
    if not users:
        raise SystemExit(f"User {USER_EMAIL} not found")
    uid = users[0]["id"]
    print(f"Clearing dummy data for {USER_EMAIL} ({uid})")

    clear_ocr_storage(c, uid)
    wipe_all(c, "ocr_staging")

    debts = c.table("debts").select("id").eq("user_id", uid).execute().data or []
    for d in debts:
        c.table("debt_transactions").delete().eq("debt_id", d["id"]).execute()
        try:
            c.table("debt_rate_history").delete().eq("debt_id", d["id"]).execute()
        except Exception:
            pass
    wipe_by_user(c, "debts", uid)
    wipe_by_user(c, "dividends", uid)
    wipe_by_user(c, "cash_flows", uid)
    wipe_by_user(c, "tax_records", uid)
    wipe_by_user(c, "other_assets", uid)
    wipe_by_user(c, "wealth_alert_events", uid)

    accts = c.table("accounts").select("id").eq("user_id", uid).execute().data or []
    for a in accts:
        aid = a["id"]
        c.table("trades").delete().eq("account_id", aid).execute()
        c.table("holdings").delete().eq("account_id", aid).execute()
        try:
            c.table("holding_daily_snapshots").delete().eq("account_id", aid).execute()
        except Exception:
            pass
        c.table("accounts").delete().eq("id", aid).execute()
    print("  cleared trades/holdings/accounts")

    try:
        c.table("daily_snapshots").delete().gte("snapshot_date", "2000-01-01").execute()
        c.table("market_index_snapshots").delete().gte("snapshot_date", "2000-01-01").execute()
        print("  cleared snapshots")
    except Exception as exc:
        print(f"  snapshot skip: {exc}")

    print("Done. Add real accounts in Next → 기록 → 계좌.")
    print("Do NOT re-run scripts/seed_dummy_data.py unless you want demo data again.")


if __name__ == "__main__":
    main()
    sys.exit(0)
