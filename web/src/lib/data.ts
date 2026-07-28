import {
  AccountRow,
  HoldingRow,
  PriceRow,
  OtherAssetRow,
  DailySnap,
  WealthAlert,
  DebtRow,
  buildLiveHoldings,
  computeNetWorth,
  aggregateByTicker,
  accountIdsForInstitution,
  filterLiveByAccountAndOwnership,
  allocationActual,
  allocationDrift,
  monthlySummaryStats,
  debtsDueSoon,
  institutionsFromAccounts,
} from "@/lib/portfolio";
import { createClient } from "@/lib/supabase/server";

export type PortfolioFilters = {
  ownership?: string | null;
  institution?: string | null;
};

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

export async function loadPortfolioSnapshot(filters: PortfolioFilters = {}) {
  const supabase = await createClient();
  const ownership =
    filters.ownership && ["joint", "mine", "spouse"].includes(filters.ownership)
      ? filters.ownership
      : null;
  const institution =
    filters.institution && filters.institution !== "전체"
      ? filters.institution
      : null;

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

  let debts = await safeSelect<DebtRow>(() =>
    supabase
      .from("debts")
      .select("id,lender,principal,due_date,ownership,interest_rate,debt_kind")
  );
  if (!debts.length) {
    debts = (
      await safeSelect<{ principal: number | null }>(() =>
        supabase.from("debts").select("principal")
      )
    ).map((d) => ({
      lender: null,
      principal: d.principal,
      due_date: null,
    }));
  }

  let otherAssets = await safeSelect<OtherAssetRow>(() =>
    supabase
      .from("other_assets")
      .select("id,name,asset_kind,value_krw,ownership,memo")
  );
  if (!otherAssets.length) {
    otherAssets = await safeSelect<OtherAssetRow>(() =>
      supabase.from("other_assets").select("value_krw,ownership")
    );
  }

  const targetRows = await safeSelect<{
    category: string;
    target_pct: number | null;
  }>(() => supabase.from("allocation_targets").select("category,target_pct"));

  const snaps = await safeSelect<DailySnap>(() =>
    supabase
      .from("daily_snapshots")
      .select(
        "snapshot_date,net_assets,total_investment,total_debt,total_cash,total_other"
      )
      .order("snapshot_date", { ascending: false })
      .limit(90)
  );

  const alerts = await safeSelect<WealthAlert>(() =>
    supabase
      .from("wealth_alert_events")
      .select("id,alert_kind,title,body,created_at")
      .eq("acknowledged", false)
      .order("created_at", { ascending: false })
      .limit(10)
  );

  const monthStart = new Date();
  monthStart.setDate(1);
  const monthIso = monthStart.toISOString().slice(0, 10);
  const realizedRows = await safeSelect<{
    pnl_krw?: number | null;
    pnl?: number | null;
  }>(() =>
    supabase
      .from("v_total_realized_pnl")
      .select("event_date,pnl_krw,pnl,currency")
      .gte("event_date", monthIso)
  );
  const realizedMonth = realizedRows.length
    ? realizedRows.reduce(
        (s, r) => s + Number(r.pnl_krw ?? r.pnl ?? 0),
        0
      )
    : null;

  const usd = priceRows.find((p) => p.ticker === "USDKRW");
  const usdkrw = usd ? Number(usd.price) : null;

  const liveAll = buildLiveHoldings(holdings, accountRows, priceRows, usdkrw);
  const accountIds = accountIdsForInstitution(accountRows, institution);

  let totalDebt = debts.reduce((s, d) => s + Number(d.principal || 0), 0);
  if (ownership) {
    totalDebt = debts
      .filter((d) => (d.ownership || "joint") === ownership)
      .reduce((s, d) => s + Number(d.principal || 0), 0);
  }

  const nw = computeNetWorth({
    live: liveAll,
    accounts: accountRows,
    otherAssets,
    totalDebt,
    usdkrw,
    accountIds,
    ownership,
  });

  const live = filterLiveByAccountAndOwnership(
    liveAll,
    accountRows,
    accountIds,
    ownership
  );
  const byTicker = aggregateByTicker(live).sort(
    (a, b) => (b.value_krw || 0) - (a.value_krw || 0)
  );

  const investCost = live.reduce((s, r) => s + (r.cost_krw || 0), 0);
  const returnPct =
    investCost > 0 ? ((nw.invest - investCost) / investCost) * 100 : null;

  const targets: Record<string, number> = {
    domestic: 0,
    overseas: 0,
    cash: 0,
    other: 0,
  };
  for (const t of targetRows) {
    if (t.category in targets) {
      targets[t.category] = Number(t.target_pct || 0);
    }
  }
  // Sensible defaults if table empty / missing
  if (targetRows.length === 0) {
    targets.domestic = 40;
    targets.overseas = 40;
    targets.cash = 15;
    targets.other = 5;
  }

  const actual = allocationActual(nw);
  const drift = allocationDrift(actual, targets);
  const monthly = monthlySummaryStats({
    liveNet: nw.net,
    snaps: [...snaps].reverse(),
    realizedMonth,
  });

  const dueDebts = debtsDueSoon(debts, 30);
  const displayAlerts: WealthAlert[] = [...alerts];
  for (const d of dueDebts) {
    const title = `부채 만기 임박 · ${d.lender || "부채"}`;
    if (displayAlerts.some((a) => a.title === title)) continue;
    displayAlerts.push({
      id: `due-${d.id || d.due}`,
      alert_kind: "debt_due",
      title,
      body: `${d.due} (${d.days}일 후) · 잔금 ${Number(d.principal || 0).toLocaleString("ko-KR")}원`,
    });
  }

  const cashAccounts = accountRows
    .filter((a) => {
      if (accountIds && !accountIds.includes(a.id)) return false;
      if (ownership && (a.ownership || "joint") !== ownership) return false;
      return Number(a.cash_balance || 0) !== 0 || a.account_type === "bank";
    })
    .map((a) => ({
      id: a.id,
      institution: a.institution || "계좌",
      account_type: a.account_type || "brokerage",
      ownership: a.ownership || "joint",
      currency: (a.currency || "KRW").toUpperCase(),
      cash_balance: Number(a.cash_balance || 0),
    }));

  return {
    live,
    byTicker,
    accounts: accountRows,
    institutions: institutionsFromAccounts(accountRows),
    otherAssets: nw.other_rows.length ? nw.other_rows : otherAssets,
    cashAccounts,
    nw,
    usdkrw,
    returnPct,
    latestSnap: snaps[0] || null,
    snaps: [...snaps].reverse(),
    allocation: drift,
    monthly,
    alerts: displayAlerts,
    filters: {
      ownership: ownership || "전체",
      institution: institution || "전체",
    },
  };
}
