"""Build a structured context blob from the couple's wealth tables."""

from __future__ import annotations

import json
from typing import Any


def _safe(rows: Any) -> list:
    return rows if isinstance(rows, list) else []


def build_wealth_context(client) -> dict[str, Any]:
    """Pull current portfolio facts for LLM grounding (no secrets)."""
    holdings = _safe(client.table("holdings").select("*").execute().data)
    prices = _safe(client.table("market_prices").select("*").execute().data)
    accounts = _safe(
        client.table("accounts").select("id,institution,account_type,currency,user_id").execute().data
    )
    debts = _safe(client.table("debts").select("*").execute().data)
    trades = _safe(
        client.table("trades")
        .select("trade_date,ticker,trade_type,price,quantity,reason,account_id")
        .order("trade_date", desc=True)
        .limit(30)
        .execute()
        .data
    )
    snaps = _safe(
        client.table("daily_snapshots")
        .select("*")
        .order("snapshot_date", desc=True)
        .limit(14)
        .execute()
        .data
    )
    tax = _safe(client.table("tax_records").select("*").execute().data)
    tax_view = _safe(client.table("v_tax_calculation").select("*").execute().data)
    portfolio = _safe(client.table("v_portfolio").select("*").execute().data)
    cash = _safe(
        client.table("cash_flows")
        .select("flow_date,category,amount,flow_type,memo")
        .order("flow_date", desc=True)
        .limit(40)
        .execute()
        .data
    )

    price_map = {p["ticker"]: p for p in prices}
    usdkrw = price_map.get("USDKRW", {}).get("price")

    enriched = []
    total_usd = 0.0
    for h in holdings:
        mp = price_map.get(h["ticker"])
        px = mp.get("price") if mp else None
        qty = float(h.get("quantity") or 0)
        avg = float(h.get("avg_price") or 0)
        ccy = h.get("currency") or (mp.get("currency") if mp else "USD") or "USD"
        mv = float(px) * qty if px is not None else None
        if mv is not None and ccy == "USD":
            total_usd += mv
        ret = ((float(px) - avg) / avg * 100) if px is not None and avg else None
        enriched.append(
            {
                "ticker": h.get("ticker"),
                "name": h.get("name"),
                "quantity": qty,
                "avg_price": avg,
                "currency": ccy,
                "current_price": px,
                "market_value": mv,
                "return_pct": ret,
                "price_updated_at": mp.get("updated_at") if mp else None,
            }
        )

    return {
        "as_of_note": "Values come only from the couple's Supabase DB.",
        "usdkrw": usdkrw,
        "accounts": accounts,
        "holdings": enriched,
        "portfolio_view": portfolio,
        "approx_investment_usd": total_usd,
        "debts": debts,
        "recent_trades": trades,
        "recent_cash_flows": cash,
        "daily_snapshots": snaps,
        "tax_records": tax,
        "tax_estimates": tax_view,
    }


def context_to_prompt_block(ctx: dict[str, Any], max_chars: int = 14000) -> str:
    text = json.dumps(ctx, ensure_ascii=False, indent=2, default=str)
    if len(text) > max_chars:
        text = text[: max_chars - 20] + "\n…(truncated)"
    return text
