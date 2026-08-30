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
  monthlySummaryStats,
  debtsDueSoon,
  institutionsFromAccounts,
} from "@/lib/portfolio";
import { createClient } from "@/lib/supabase/server";
import { monthStartKst } from "@/lib/dates";

export type PortfolioFilters = {
  ownership?: string | null;
  institution?: string | null;
};

export class DataLoadError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DataLoadError";
  }
}

async function safeSelect<T>(
  run: () => PromiseLike<{ data: T[] | null; error: { message: string } | null }>,
  opts?: { optional?: boolean; label?: string }
): Promise<T[]> {
  const label = opts?.label || "query";
  try {
    const { data, error } = await run();
    if (error) {
      console.error(`[data] ${label}:`, error.message);
      if (opts?.optional) return [];
      throw new DataLoadError(`데이터 로드 실패 (${label}): ${error.message}`);
    }
    return data || [];
  } catch (e) {
    if (e instanceof DataLoadError) throw e;
    console.error(`[data] ${label}:`, e);
    if (opts?.optional) return [];
    throw new DataLoadError(
      `데이터 로드 실패 (${label}): ${e instanceof Error ? e.message : "unknown"}`
    );
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

  let accountRows = await safeSelect<AccountRow>(
    () =>
      supabase
        .from("accounts")
        .select("id,institution,account_type,currency,ownership,cash_balance,memo"),
    { optional: true, label: "accounts" }
  );
  if (!accountRows.length) {
    accountRows = (
      await safeSelect<AccountRow>(
        () =>
          supabase
            .from("accounts")
            .select("id,institution,account_type,currency,ownership,cash_balance"),
        { optional: true, label: "accounts-no-memo" }
      )
    ).map((a) => ({ ...a, memo: null }));
  }
  if (!accountRows.length) {
    accountRows = (
      await safeSelect<AccountRow>(
        () =>
          supabase
            .from("accounts")
            .select("id,institution,account_type,currency,ownership"),
        { optional: true, label: "accounts-ownership" }
      )
    ).map((a) => ({ ...a, cash_balance: 0, memo: null }));
  }
  if (!accountRows.length) {
    accountRows = (
      await safeSelect<AccountRow>(
        () =>
          supabase
            .from("accounts")
            .select("id,institution,account_type,currency"),
        { label: "accounts-lean" }
      )
    ).map((a) => ({ ...a, ownership: "mine", cash_balance: 0, memo: null }));
  }

  const monthIso = monthStartKst();

  const [
    holdings,
    priceRows,
    debtsRaw,
    otherRaw,
    snaps,
    alerts,
    realizedRows,
  ] = await Promise.all([
    safeSelect<HoldingRow>(() => supabase.from("holdings").select("*"), {
      label: "holdings",
    }),
    safeSelect<PriceRow>(
      () =>
        supabase.from("market_prices").select("ticker,price,currency,updated_at"),
      { optional: true, label: "market_prices" }
    ),
    safeSelect<DebtRow>(
      () =>
        supabase
          .from("debts")
          .select("id,lender,principal,due_date,ownership,interest_rate,debt_kind"),
      { optional: true, label: "debts" }
    ),
    safeSelect<OtherAssetRow>(
      () =>
        supabase
          .from("other_assets")
          .select("id,name,asset_kind,value_krw,cost_krw,ownership,memo"),
      { optional: true, label: "other_assets" }
    ),
    safeSelect<DailySnap>(
      () =>
        supabase
          .from("daily_snapshots")
          .select(
            "snapshot_date,net_assets,total_investment,total_debt,total_cash,total_other"
          )
          .order("snapshot_date", { ascending: false })
          .limit(400),
      { optional: true, label: "daily_snapshots" }
    ),
    safeSelect<WealthAlert>(
      () =>
        supabase
          .from("wealth_alert_events")
          .select("id,alert_kind,title,body,created_at")
          .eq("acknowledged", false)
          .order("created_at", { ascending: false })
          .limit(10),
      { optional: true, label: "wealth_alerts" }
    ),
    safeSelect<{ pnl_krw?: number | null; pnl?: number | null }>(
      () =>
        supabase
          .from("v_total_realized_pnl")
          .select("event_date,pnl_krw,pnl,currency")
          .gte("event_date", monthIso),
      { optional: true, label: "v_total_realized_pnl" }
    ),
  ]);

  let debts = debtsRaw;
  if (!debts.length) {
    debts = (
      await safeSelect<{ principal: number | null }>(
        () => supabase.from("debts").select("principal"),
        { optional: true, label: "debts-lean" }
      )
    ).map((d) => ({
      lender: null,
      principal: d.principal,
      due_date: null,
    }));
  }

  let otherAssets = otherRaw;
  if (!otherAssets.length) {
    otherAssets = (
      await safeSelect<OtherAssetRow>(
        () =>
          supabase
            .from("other_assets")
            .select("id,name,asset_kind,value_krw,ownership,memo"),
        { optional: true, label: "other_assets-no-cost" }
      )
    ).map((a) => ({ ...a, cost_krw: null }));
  }
  if (!otherAssets.length) {
    otherAssets = await safeSelect<OtherAssetRow>(
      () => supabase.from("other_assets").select("value_krw,ownership"),
      { optional: true, label: "other_assets-lean" }
    );
  }

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
      memo: a.memo || null,
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
    monthly,
    alerts: displayAlerts,
    filters: {
      ownership: ownership || "전체",
      institution: institution || "전체",
    },
  };
}
