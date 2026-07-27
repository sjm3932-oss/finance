import {
  AccountRow,
  HoldingRow,
  PriceRow,
  buildLiveHoldings,
  computeNetWorth,
  aggregateByTicker,
} from "@/lib/portfolio";
import { createClient } from "@/lib/supabase/server";

async function safeSelect<T>(
  run: () => PromiseLike<{ data: T[] | null; error: { message: string } | null }>
): Promise<T[]> {
  try {
    const { data, error } = await run();
    if (error) return [];
    return data || [];
  } catch {
    return [];
  }
}

export async function loadPortfolioSnapshot() {
  const supabase = await createClient();

  let accountRows = await safeSelect<AccountRow>(() =>
    supabase
      .from("accounts")
      .select("id,institution,account_type,currency,ownership,cash_balance")
  );
  if (!accountRows.length) {
    accountRows = (
      await safeSelect<AccountRow>(() =>
        supabase
          .from("accounts")
          .select("id,institution,account_type,currency")
      )
    ).map((a) => ({ ...a, ownership: "joint", cash_balance: 0 }));
  }

  const holdings = await safeSelect<HoldingRow>(() =>
    supabase.from("holdings").select("*")
  );
  const priceRows = await safeSelect<PriceRow>(() =>
    supabase.from("market_prices").select("ticker,price,currency,updated_at")
  );
  const debts = await safeSelect<{ principal: number | null }>(() =>
    supabase.from("debts").select("principal")
  );
  const otherAssets = await safeSelect<{
    value_krw?: number | null;
    ownership?: string | null;
  }>(() => supabase.from("other_assets").select("value_krw,ownership"));
  const snaps = await safeSelect<Record<string, unknown>>(() =>
    supabase
      .from("daily_snapshots")
      .select(
        "snapshot_date,net_assets,total_investment,total_debt,total_cash,total_other"
      )
      .order("snapshot_date", { ascending: false })
      .limit(1)
  );

  const usd = priceRows.find((p) => p.ticker === "USDKRW");
  const usdkrw = usd ? Number(usd.price) : null;

  const live = buildLiveHoldings(holdings, accountRows, priceRows, usdkrw);
  const totalDebt = debts.reduce((s, d) => s + Number(d.principal || 0), 0);

  const nw = computeNetWorth({
    live,
    accounts: accountRows,
    otherAssets,
    totalDebt,
    usdkrw,
  });

  const byTicker = aggregateByTicker(live).sort(
    (a, b) => (b.value_krw || 0) - (a.value_krw || 0)
  );

  const investCost = live.reduce((s, r) => s + (r.cost_krw || 0), 0);
  const returnPct =
    investCost > 0 ? ((nw.invest - investCost) / investCost) * 100 : null;

  return {
    live,
    byTicker,
    accounts: accountRows,
    nw,
    usdkrw,
    returnPct,
    latestSnap: snaps[0] || null,
  };
}
