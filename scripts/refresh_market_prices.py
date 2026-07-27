#!/usr/bin/env python3
"""Refresh market_prices (+ optional USD/KRW) — Naver KR / Yahoo US / Frankfurter FX."""

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

from lib.market_data import (  # noqa: E402
    fetch_market_indices,
    fetch_usdkrw,
    refresh_tickers,
    sync_holding_names,
)
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
        price_rows = [
            {k: r[k] for k in ("ticker", "price", "currency", "updated_at") if k in r}
            for r in rows
        ]
        client.table("market_prices").upsert(price_rows, on_conflict="ticker").execute()
        n = sync_holding_names(client, rows)
        print(f"upserted {len(rows)} prices; synced {n} holding names")
        for r in rows:
            print(f"  {r['ticker']}: {r['price']} {r['currency']} ({r.get('name') or '—'})")
    for e in errors:
        print(f"warn: {e}", file=sys.stderr)

    index_row: dict = {"snapshot_date": date.today().isoformat()}
    try:
        usdkrw = fetch_usdkrw()
        index_row["usdkrw"] = usdkrw
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

    try:
        indices, idx_errs = fetch_market_indices()
        index_row.update(indices)
        for e in idx_errs:
            print(f"warn: index {e}", file=sys.stderr)
        print(f"indices={indices}")
    except Exception as exc:  # noqa: BLE001
        print(f"warn: indices failed: {exc}", file=sys.stderr)

    if len(index_row) > 1:
        try:
            client.table("market_index_snapshots").upsert(
                index_row, on_conflict="snapshot_date"
            ).execute()
        except Exception as exc:  # noqa: BLE001
            print(f"warn: index snapshot upsert failed: {exc}", file=sys.stderr)

    return 0 if rows or not tickers else 1


if __name__ == "__main__":
    raise SystemExit(main())
