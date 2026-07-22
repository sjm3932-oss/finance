#!/usr/bin/env python3
"""Refresh market_prices (+ optional USD/KRW index snapshot) from Yahoo/Frankfurter."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "streamlit_app"))
load_dotenv(ROOT / ".env")

from lib.market_data import fetch_usdkrw, refresh_tickers  # noqa: E402
from lib.supabase_client import get_service_client  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tickers",
        nargs="*",
        help="Explicit tickers; default = distinct holdings tickers",
    )
    args = parser.parse_args()

    client = get_service_client()
    if args.tickers:
        tickers = args.tickers
    else:
        holdings = client.table("holdings").select("ticker").execute().data or []
        tickers = [h["ticker"] for h in holdings]

    rows, errors = refresh_tickers(tickers)
    if rows:
        client.table("market_prices").upsert(rows, on_conflict="ticker").execute()
        print(f"upserted {len(rows)} prices")
        for r in rows:
            print(f"  {r['ticker']}: {r['price']} {r['currency']}")
    for e in errors:
        print(f"warn: {e}", file=sys.stderr)

    try:
        usdkrw = fetch_usdkrw()
        client.table("market_index_snapshots").upsert(
            {
                "snapshot_date": date.today().isoformat(),
                "usdkrw": usdkrw,
            },
            on_conflict="snapshot_date",
        ).execute()
        # also store FX as pseudo ticker for joins if useful
        client.table("market_prices").upsert(
            {
                "ticker": "USDKRW",
                "price": usdkrw,
                "currency": "KRW",
            },
            on_conflict="ticker",
        ).execute()
        print(f"USD/KRW={usdkrw}")
    except Exception as exc:  # noqa: BLE001
        print(f"warn: FX failed: {exc}", file=sys.stderr)

    return 0 if rows or not tickers else 1


if __name__ == "__main__":
    raise SystemExit(main())
