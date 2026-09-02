#!/usr/bin/env python3
"""Clear OCR uploads + transactional data, then seed detailed dummy data.

Keeps the logged-in couple user. Rebuilds accounts, trades (with realized P&L),
dividends, cash flows, debts, market prices, and daily holding snapshots so
대시보드 / 실현손익 charts have rich monthly history.

Usage:
  cd /workspace && .venv/bin/python scripts/seed_dummy_data.py
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

USER_EMAIL = "sjm3932@gmail.com"

# Approximate “current” prices for snapshots / market_prices
PRICES = {
    "AAPL": (210.0, "USD"),
    "MSFT": (430.0, "USD"),
    "NVDA": (120.0, "USD"),
    "QQQM": (200.0, "USD"),
    "SCHD": (28.0, "USD"),
    "JEPI": (56.0, "USD"),
    "TQQQ": (72.0, "USD"),
    "005930": (78000.0, "KRW"),  # Samsung
    "000660": (210000.0, "KRW"),  # SK hynix
    "USDKRW": (1380.0, "KRW"),
}


def client():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def wipe_table(c, table: str, *, eq: tuple[str, str] | None = None) -> int:
    q = c.table(table).delete()
    if eq:
        q = q.eq(eq[0], eq[1])
    else:
        # PostgREST needs a filter; match all non-null primary-ish columns via gte on created
        q = q.neq("id", "00000000-0000-0000-0000-000000000000")
    res = q.execute()
    n = len(res.data or [])
    print(f"  cleared {table}: ~{n}")
    return n


def wipe_by_user(c, table: str, user_id: str) -> None:
    c.table(table).delete().eq("user_id", user_id).execute()
    print(f"  cleared {table} for user")


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


def month_ends(start: date, end: date) -> list[date]:
    out: list[date] = []
    y, m = start.year, start.month
    while True:
        if m == 12:
            d = date(y, 12, 31)
            y, m = y + 1, 1
        else:
            d = date(y, m + 1, 1) - timedelta(days=1)
            m += 1
        if d < start:
            continue
        if d > end:
            break
        out.append(d)
    return out


def seed(c) -> None:
    users = c.table("users").select("*").eq("email", USER_EMAIL).execute().data or []
    if not users:
        raise SystemExit(f"User {USER_EMAIL} not found — log in once first")
    user = users[0]
    uid = user["id"]
    print(f"Seeding for {user['email']} ({uid})")

    # ---- 1) Clear OCR + transactional data ----
    print("Clearing OCR + ledger data…")
    clear_ocr_storage(c, uid)
    wipe_table(c, "ocr_staging")

    # debt txs before debts
    debts = c.table("debts").select("id").eq("user_id", uid).execute().data or []
    for d in debts:
        c.table("debt_transactions").delete().eq("debt_id", d["id"]).execute()
    wipe_by_user(c, "debts", uid)
    wipe_by_user(c, "dividends", uid)
    wipe_by_user(c, "cash_flows", uid)
    wipe_by_user(c, "tax_records", uid)

    # trades / holdings / snapshots (account-scoped)
    accts = c.table("accounts").select("id").eq("user_id", uid).execute().data or []
    for a in accts:
        aid = a["id"]
        c.table("trades").delete().eq("account_id", aid).execute()
        c.table("holdings").delete().eq("account_id", aid).execute()
        c.table("holding_daily_snapshots").delete().eq("account_id", aid).execute()
    print("  cleared trades/holdings/holding_daily_snapshots")

    # daily snapshots are global for the couple DB
    c.table("daily_snapshots").delete().gte("snapshot_date", "2000-01-01").execute()
    c.table("market_index_snapshots").delete().gte("snapshot_date", "2000-01-01").execute()
    print("  cleared daily_snapshots / market_index_snapshots")

    # recreate accounts cleanly
    for a in accts:
        c.table("accounts").delete().eq("id", a["id"]).execute()
    print("  cleared accounts")

    # ---- 2) Accounts ----
    print("Creating accounts…")
    def add_account(institution: str, account_type: str, currency: str) -> str:
        row = (
            c.table("accounts")
            .insert(
                {
                    "user_id": uid,
                    "institution": institution,
                    "account_type": account_type,
                    "currency": currency,
                }
            )
            .execute()
            .data[0]
        )
        print(f"  + {institution} ({account_type}/{currency})")
        return row["id"]

    toss = add_account("토스증권", "brokerage", "USD")
    kiwoom = add_account("키움증권", "brokerage", "KRW")
    kakao = add_account("카카오뱅크", "bank", "KRW")

    # ---- 3) Market prices ----
    print("Upserting market prices…")
    for ticker, (price, ccy) in PRICES.items():
        c.table("market_prices").upsert(
            {"ticker": ticker, "price": price, "currency": ccy},
            on_conflict="ticker",
        ).execute()

    # ---- 4) Trades (chronological — trigger builds holdings + realized_pnl) ----
    print("Inserting trades…")
    # (date, account, ticker, type, price, qty, fee, reason)
    trades: list[tuple] = [
        # 2025 accumulation
        ("2025-01-10", toss, "AAPL", "buy", 185.0, 20, 1.0, "연초 적립"),
        ("2025-01-10", toss, "MSFT", "buy", 390.0, 8, 1.0, "연초 적립"),
        ("2025-01-15", toss, "SCHD", "buy", 26.5, 100, 1.0, "배당주 적립"),
        ("2025-02-05", toss, "JEPI", "buy", 55.0, 80, 1.0, "월배당 적립"),
        ("2025-02-20", toss, "QQQM", "buy", 180.0, 15, 1.0, "나스닥 적립"),
        ("2025-03-12", toss, "NVDA", "buy", 95.0, 30, 1.5, "성장주"),
        ("2025-03-12", toss, "TQQQ", "buy", 55.0, 40, 1.5, "레버리지 ETF"),
        ("2025-04-08", kiwoom, "005930", "buy", 72000, 50, 0, "삼성전자 적립"),
        ("2025-04-08", kiwoom, "000660", "buy", 180000, 10, 0, "SK하이닉스"),
        ("2025-05-14", toss, "AAPL", "buy", 195.0, 10, 1.0, "추가 매수"),
        ("2025-05-14", toss, "SCHD", "buy", 27.0, 50, 1.0, "배당 재투자"),
        ("2025-06-20", toss, "MSFT", "buy", 410.0, 5, 1.0, "추가 매수"),
        ("2025-07-09", toss, "JEPI", "buy", 55.5, 40, 1.0, "월배당 추가"),
        ("2025-08-11", toss, "NVDA", "buy", 105.0, 20, 1.5, "추가 매수"),
        ("2025-09-03", toss, "QQQM", "buy", 190.0, 10, 1.0, "추가 매수"),
        ("2025-09-18", kiwoom, "005930", "buy", 74000, 30, 0, "추가 매수"),
        # Realized sells (gains / losses)
        ("2025-10-15", toss, "AAPL", "sell", 225.0, 15, 2.0, "일부 익절"),
        ("2025-10-22", toss, "TQQQ", "sell", 48.0, 20, 2.0, "변동성 축소"),
        ("2025-11-12", toss, "NVDA", "sell", 135.0, 15, 2.0, "익절"),
        ("2025-12-05", kiwoom, "005930", "sell", 76000, 20, 0, "일부 매도"),
        ("2025-12-18", toss, "MSFT", "sell", 400.0, 4, 1.5, "리밸런싱"),
        # 2026
        ("2026-01-08", toss, "SCHD", "buy", 27.5, 60, 1.0, "연초 배당 적립"),
        ("2026-01-08", toss, "JEPI", "buy", 56.0, 50, 1.0, "연초 월배당"),
        ("2026-02-14", toss, "AAPL", "buy", 200.0, 8, 1.0, "밸런타인 적립"),
        ("2026-03-10", toss, "QQQM", "buy", 195.0, 8, 1.0, "적립"),
        ("2026-03-25", toss, "NVDA", "sell", 110.0, 10, 1.5, "일부 익절"),
        ("2026-04-16", kiwoom, "000660", "buy", 195000, 5, 0, "추가 매수"),
        ("2026-05-07", toss, "TQQQ", "buy", 65.0, 25, 1.5, "반등 매수"),
        ("2026-05-21", toss, "SCHD", "sell", 29.0, 40, 1.0, "배당주 일부 익절"),
        ("2026-06-11", toss, "JEPI", "sell", 57.5, 30, 1.0, "월배당 일부 익절"),
        ("2026-06-28", toss, "MSFT", "buy", 425.0, 4, 1.0, "하반기 적립"),
        ("2026-07-10", toss, "AAPL", "sell", 215.0, 5, 1.0, "리밸런싱"),
        ("2026-07-15", kiwoom, "005930", "buy", 77500, 20, 0, "최근 적립"),
    ]

    for td, acct, ticker, ttype, price, qty, fee, reason in trades:
        ccy = "KRW" if acct == kiwoom else "USD"
        c.table("trades").insert(
            {
                "account_id": acct,
                "trade_date": td,
                "ticker": ticker,
                "trade_type": ttype,
                "price": price,
                "quantity": qty,
                "fee": fee,
                "currency": ccy,
                "reason": reason,
                "memo": reason,
                "created_by": uid,
                "adjust_holdings": True,
            }
        ).execute()
    print(f"  + {len(trades)} trades")

    # ---- 5) Dividends (monthly income names) ----
    print("Inserting dividends…")
    dividends: list[dict] = []
    # SCHD / JEPI quarterly-ish + monthly JEPI-style
    schd_pays = [
        ("2025-03-28", 42.0),
        ("2025-06-27", 48.0),
        ("2025-09-26", 55.0),
        ("2025-12-27", 62.0),
        ("2026-03-28", 70.0),
        ("2026-06-27", 78.0),
    ]
    for pay, amt in schd_pays:
        dividends.append(
            {
                "user_id": uid,
                "account_id": toss,
                "ticker": "SCHD",
                "name": "Schwab US Dividend Equity ETF",
                "pay_date": pay,
                "amount": amt,
                "currency": "USD",
                "memo": "분기 배당",
            }
        )

    # JEPI monthly
    jepi_months = [
        (2025, m, round(35 + m * 0.8 + (i % 3), 2))
        for i, m in enumerate(range(2, 13))
    ] + [(2026, m, round(45 + m * 0.6, 2)) for m in range(1, 7)]
    for y, m, amt in jepi_months:
        dividends.append(
            {
                "user_id": uid,
                "account_id": toss,
                "ticker": "JEPI",
                "name": "JPMorgan Equity Premium Income ETF",
                "pay_date": f"{y}-{m:02d}-28" if m != 2 else f"{y}-02-26",
                "amount": amt,
                "currency": "USD",
                "memo": "월배당",
            }
        )

    # AAPL / MSFT annual-ish
    for pay, ticker, amt, name in [
        ("2025-05-15", "AAPL", 12.5, "Apple"),
        ("2025-08-14", "AAPL", 13.0, "Apple"),
        ("2025-11-14", "AAPL", 13.5, "Apple"),
        ("2026-02-13", "AAPL", 14.0, "Apple"),
        ("2026-05-15", "AAPL", 14.5, "Apple"),
        ("2025-06-12", "MSFT", 18.0, "Microsoft"),
        ("2025-09-11", "MSFT", 19.0, "Microsoft"),
        ("2025-12-11", "MSFT", 20.0, "Microsoft"),
        ("2026-03-13", "MSFT", 21.0, "Microsoft"),
        ("2026-06-12", "MSFT", 22.0, "Microsoft"),
        ("2025-06-20", "005930", 45000, "삼성전자"),
        ("2025-12-19", "005930", 52000, "삼성전자"),
        ("2026-06-19", "005930", 55000, "삼성전자"),
    ]:
        dividends.append(
            {
                "user_id": uid,
                "account_id": kiwoom if ticker == "005930" else toss,
                "ticker": ticker,
                "name": name,
                "pay_date": pay,
                "amount": amt,
                "currency": "KRW" if ticker == "005930" else "USD",
                "memo": "배당금",
            }
        )

    # chunk insert
    for i in range(0, len(dividends), 40):
        c.table("dividends").insert(dividends[i : i + 40]).execute()
    print(f"  + {len(dividends)} dividends")

    # ---- 6) Cash flows (salary, expenses, interest income) ----
    print("Inserting cash flows…")
    flows: list[dict] = []
    for y, m in [(2025, mm) for mm in range(1, 13)] + [(2026, mm) for mm in range(1, 8)]:
        flows.append(
            {
                "user_id": uid,
                "account_id": kakao,
                "flow_date": f"{y}-{m:02d}-25",
                "category": "월급",
                "amount": 5_200_000 if y == 2025 else 5_500_000,
                "flow_type": "income",
                "currency": "KRW",
                "memo": "부부 합산 월급(더미)",
            }
        )
        flows.append(
            {
                "user_id": uid,
                "account_id": kakao,
                "flow_date": f"{y}-{m:02d}-05",
                "category": "생활비",
                "amount": 1_800_000,
                "flow_type": "expense",
                "currency": "KRW",
                "memo": "생활비",
            }
        )
        flows.append(
            {
                "user_id": uid,
                "account_id": kakao,
                "flow_date": f"{y}-{m:02d}-10",
                "category": "주거",
                "amount": 900_000,
                "flow_type": "expense",
                "currency": "KRW",
                "memo": "관리비·공과금",
            }
        )
        # Interest income (은행 예금 이자) — feeds realized PnL view
        if m in (3, 6, 9, 12) or (y == 2026 and m in (3, 6)):
            flows.append(
                {
                    "user_id": uid,
                    "account_id": kakao,
                    "flow_date": f"{y}-{m:02d}-15",
                    "category": "이자",
                    "amount": 85_000 + m * 1_500,
                    "flow_type": "income",
                    "currency": "KRW",
                    "memo": "예금 이자",
                }
            )

    for i in range(0, len(flows), 50):
        c.table("cash_flows").insert(flows[i : i + 50]).execute()
    print(f"  + {len(flows)} cash flows")

    # ---- 7) Debt + interest / repayment ----
    print("Inserting debt…")
    debt = (
        c.table("debts")
        .insert(
            {
                "user_id": uid,
                "lender": "KB국민은행 주택담보대출",
                "principal": 180_000_000,  # starting; txs will adjust
                "original_principal": 200_000_000,
                "interest_rate": 3.8,
                "started_on": "2015-06-30",
                "due_date": "2045-06-30",
                "repay_method": "equal_payment",
                "grace_months": 0,
                "memo": "더미 주담대",
            }
        )
        .execute()
        .data[0]
    )
    debt_id = debt["id"]
    # Set principal baseline via txs carefully:
    # Insert starts at 180M; repayment reduces; interest capitalizes.
    debt_txs = [
        ("2025-01-31", "interest", 570_000, "1월 이자"),
        ("2025-01-31", "repayment", 800_000, "1월 원금상환"),
        ("2025-04-30", "interest", 560_000, "2Q 이자"),
        ("2025-04-30", "repayment", 850_000, "2Q 원금상환"),
        ("2025-07-31", "interest", 550_000, "3Q 이자"),
        ("2025-07-31", "repayment", 900_000, "3Q 원금상환"),
        ("2025-10-31", "interest", 540_000, "4Q 이자"),
        ("2025-10-31", "repayment", 950_000, "4Q 원금상환"),
        ("2026-01-31", "interest", 530_000, "26 1Q 이자"),
        ("2026-01-31", "repayment", 1_000_000, "26 1Q 원금상환"),
        ("2026-04-30", "interest", 520_000, "26 2Q 이자"),
        ("2026-04-30", "repayment", 1_050_000, "26 2Q 원금상환"),
        ("2026-07-15", "interest", 510_000, "최근 이자"),
        ("2026-07-15", "repayment", 1_100_000, "최근 원금상환"),
    ]
    for tx_date, tx_type, amount, memo in debt_txs:
        c.table("debt_transactions").insert(
            {
                "debt_id": debt_id,
                "user_id": uid,
                "tx_date": tx_date,
                "tx_type": tx_type,
                "amount": amount,
                "memo": memo,
            }
        ).execute()
    print(f"  + debt + {len(debt_txs)} debt transactions")

    # ---- 8) Tax record ----
    c.table("tax_records").insert(
        {
            "user_id": uid,
            "tax_year": 2026,
            "cum_capital_gain": 1_250_000,
            "tax_threshold": 2_500_000,
            "dividend_tax": 85_000,
        }
    ).execute()

    # ---- 9) Holding daily snapshots (month-ends + recent days) ----
    print("Building holding daily snapshots…")
    holdings = c.table("holdings").select("*").execute().data or []
    print(f"  current holdings: {len(holdings)}")
    for h in holdings:
        print(f"    {h['ticker']} qty={h['quantity']} avg={h['avg_price']} @acct={h['account_id'][:8]}")

    usdkrw = PRICES["USDKRW"][0]
    # Use current holdings for recent month-ends (simplified demo history).
    # Vary price ±8% by month so charts move.
    ends = month_ends(date(2025, 1, 31), date(2026, 6, 30))
    # also last ~10 calendar days
    today = date(2026, 7, 22)
    recent = [today - timedelta(days=i) for i in range(10, -1, -1)]
    snap_dates = sorted(set(ends + recent))

    rows: list[dict] = []
    for i, d in enumerate(snap_dates):
        drift = 0.92 + (i / max(len(snap_dates) - 1, 1)) * 0.16  # 0.92 → 1.08
        for h in holdings:
            ticker = h["ticker"]
            base, ccy = PRICES.get(ticker, (float(h["avg_price"] or 1), h.get("currency") or "USD"))
            px = round(float(base) * drift, 4)
            qty = float(h["quantity"])
            mv = qty * px
            mv_krw = mv * usdkrw if ccy == "USD" else mv
            avg = float(h["avg_price"] or 0)
            ret = ((px - avg) / avg) if avg else None
            rows.append(
                {
                    "snapshot_date": d.isoformat(),
                    "account_id": h["account_id"],
                    "ticker": ticker,
                    "name": h.get("name") or ticker,
                    "quantity": qty,
                    "avg_price": avg,
                    "price": px,
                    "currency": ccy,
                    "market_value": round(mv, 4),
                    "market_value_krw": round(mv_krw, 2),
                    "return_rate": round(ret, 6) if ret is not None else None,
                    "usdkrw": usdkrw,
                }
            )

    for i in range(0, len(rows), 80):
        c.table("holding_daily_snapshots").upsert(
            rows[i : i + 80],
            on_conflict="snapshot_date,account_id,ticker",
        ).execute()
    print(f"  + {len(rows)} holding_daily_snapshots across {len(snap_dates)} dates")

    # Aggregate daily_snapshots from holdings
    print("Computing daily_snapshots via RPC…")
    for d in snap_dates[-12:]:  # last year of month-ends + recent; RPC overwrites
        try:
            c.rpc("compute_daily_snapshot", {"p_date": d.isoformat()}).execute()
        except Exception as exc:
            print(f"  rpc {d}: {exc}")
    # Ensure today
    c.rpc("compute_daily_snapshot", {"p_date": today.isoformat()}).execute()

    # Market index snapshots (sparse)
    idx_rows = []
    for d in ends + [today]:
        idx_rows.append(
            {
                "snapshot_date": d.isoformat(),
                "nasdaq": 18000 + (d.toordinal() % 400),
                "sp500": 5200 + (d.toordinal() % 200),
                "usdkrw": usdkrw + (d.month - 6) * 3,
            }
        )
    c.table("market_index_snapshots").upsert(idx_rows, on_conflict="snapshot_date").execute()

    # ---- Summary ----
    print("\nDone. Counts:")
    for t in [
        "accounts",
        "holdings",
        "trades",
        "dividends",
        "cash_flows",
        "debts",
        "debt_transactions",
        "ocr_staging",
        "holding_daily_snapshots",
        "daily_snapshots",
    ]:
        n = c.table(t).select("*", count="exact").limit(1).execute().count
        print(f"  {t}: {n}")


if __name__ == "__main__":
    seed(client())
