import { monthStartKst } from "@/lib/dates";
import { marketRegion } from "@/lib/money";

export type AccountRow = {
  id: string;
  institution: string | null;
  account_type: string | null;
  currency: string | null;
  ownership?: string | null;
  cash_balance?: number | null;
  memo?: string | null;
};

export type HoldingRow = {
  id: string;
  account_id: string;
  ticker: string;
  name: string | null;
  quantity: number;
  avg_price: number;
  currency: string | null;
};

export type PriceRow = {
  ticker: string;
  price: number;
  currency: string | null;
  updated_at?: string | null;
};

export type OtherAssetRow = {
  id?: string;
  name: string | null;
  asset_kind: string | null;
  value_krw: number | null;
  cost_krw?: number | null;
  ownership: string | null;
  memo?: string | null;
};

export type LiveHolding = {
  ticker: string;
  name: string;
  account_id: string;
  institution: string;
  qty: number;
  avg: number;
  price: number | null;
  value: number | null;
  value_krw: number | null;
  cost_krw: number | null;
  return_pct: number | null;
  ccy: string;
  region: string;
  ownership: string;
};

export type NetWorth = {
  invest: number;
  cash: number;
  other: number;
  debt: number;
  gross: number;
  net: number;
  domestic: number;
  overseas: number;
  cash_ratio: number;
  other_rows: OtherAssetRow[];
};

export type MonthlySummary = {
  month_start: string;
  nw_start: number | null;
  nw_now: number | null;
  nw_change: number | null;
  nw_change_pct: number | null;
  realized_month: number | null;
};

export type WealthAlert = {
  id: string;
  alert_kind: string;
  title: string;
  body: string | null;
  created_at?: string | null;
};

export type DebtRow = {
  id?: string;
  lender: string | null;
  principal: number | null;
  due_date: string | null;
  ownership?: string | null;
  interest_rate?: number | null;
  debt_kind?: string | null;
};

export type DailySnap = {
  snapshot_date: string;
  net_assets: number | null;
  total_investment?: number | null;
  total_debt?: number | null;
  total_cash?: number | null;
  total_other?: number | null;
};

export const OWNERSHIP_KO: Record<string, string> = {
  joint: "공동",
  mine: "정명",
  spouse: "지수",
};

export const ASSET_KIND_KO: Record<string, string> = {
  real_estate: "부동산",
  pension: "연금",
  insurance: "보험",
  deposit: "예적금",
  crypto: "암호화폐",
  other: "기타",
};

function toKrw(amount: number, ccy: string, usdkrw: number | null): number {
  if ((ccy || "KRW").toUpperCase() === "USD") {
    return usdkrw ? amount * usdkrw : 0;
  }
  return amount;
}

export function buildLiveHoldings(
  holdings: HoldingRow[],
  accounts: AccountRow[],
  prices: PriceRow[],
  usdkrw: number | null
): LiveHolding[] {
  const amap = new Map(accounts.map((a) => [a.id, a]));
  const pmap = new Map(prices.map((p) => [p.ticker, p]));

  return holdings.map((h) => {
    const acct = amap.get(h.account_id);
    const mp = pmap.get(h.ticker);
    const qty = Number(h.quantity || 0);
    const avg = Number(h.avg_price || 0);
    const price = mp?.price ?? (avg > 0 ? avg : null);
    // Prefer holding currency → price currency → account currency → KRW
    // (never assume USD; that silently breaks KRW tickers)
    const ccy = (
      h.currency ||
      mp?.currency ||
      acct?.currency ||
      "KRW"
    ).toUpperCase();
    const value = price !== null ? price * qty : null;
    const value_krw = value !== null ? toKrw(value, ccy, usdkrw) : null;
    const cost_krw = toKrw(qty * avg, ccy, usdkrw);
    const return_pct =
      price !== null && avg > 0 ? ((price - avg) / avg) * 100 : null;
    const name =
      h.name && h.name.trim().toUpperCase() !== h.ticker.toUpperCase()
        ? h.name
        : h.ticker;

    return {
      ticker: h.ticker,
      name,
      account_id: h.account_id,
      institution: accountDisplayName({
        institution: acct?.institution || "계좌",
        memo: acct?.memo ?? null,
        currency: acct?.currency ?? null,
      }),
      qty,
      avg,
      price,
      value,
      value_krw,
      cost_krw,
      return_pct,
      ccy,
      region: marketRegion(h.ticker, ccy),
      ownership: acct?.ownership || "joint",
    };
  });
}

export function aggregateByTicker(rows: LiveHolding[]) {
  const groups = new Map<string, LiveHolding[]>();
  for (const r of rows) {
    const list = groups.get(r.ticker) || [];
    list.push(r);
    groups.set(r.ticker, list);
  }

  return [...groups.entries()].map(([ticker, list]) => {
    const qty = list.reduce((s, r) => s + r.qty, 0);
    const cost = list.reduce((s, r) => s + r.qty * r.avg, 0);
    const value_krw = list.reduce((s, r) => s + (r.value_krw || 0), 0);
    const value = list.every((r) => r.value !== null)
      ? list.reduce((s, r) => s + (r.value || 0), 0)
      : null;
    const avg = qty > 0 ? cost / qty : 0;
    const price = list.find((r) => r.price !== null)?.price ?? null;
    const ccy = list[0]?.ccy || "KRW";
    const return_pct =
      price !== null && avg > 0 ? ((price - avg) / avg) * 100 : null;
    const name =
      list.find(
        (r) => r.name && r.name.toUpperCase() !== r.ticker.toUpperCase()
      )?.name || ticker;

    return {
      ticker,
      name,
      qty,
      avg,
      price,
      value,
      value_krw,
      return_pct,
      ccy,
      accounts: list.length,
      institution:
        list.length === 1 ? list[0].institution : `${list.length}개 계좌`,
    };
  });
}

export function accountProductCode(memo?: string | null): string | null {
  const s = String(memo || "").trim();
  if (!s || s.includes("합산") || s.includes("·")) return null;
  if (/^\d{2}\b/.test(s)) return s.slice(0, 2);
  return null;
}

export function accountSubLabel(a: Pick<AccountRow, "memo" | "currency">): string {
  const code = accountProductCode(a.memo);
  if (code) {
    const rest = String(a.memo || "")
      .trim()
      .slice(2)
      .trim();
    return rest ? `${code} ${rest}` : code;
  }
  return String(a.currency || "KRW").toUpperCase();
}

export function accountSubKey(a: Pick<AccountRow, "id" | "memo" | "currency">): string {
  return accountProductCode(a.memo) || String(a.currency || "KRW").toUpperCase();
}

export function accountDisplayName(a: Pick<AccountRow, "institution" | "memo" | "currency">): string {
  const inst = a.institution || "계좌";
  const code = accountProductCode(a.memo);
  if (code) return `${inst} · ${accountSubLabel(a)}`;
  return inst;
}

export function groupAccountsByInstitution<T extends AccountRow>(
  accounts: T[]
): Array<{ institution: string; accounts: T[] }> {
  const order: string[] = [];
  const map = new Map<string, T[]>();
  for (const a of accounts) {
    const inst = a.institution || "계좌";
    if (!map.has(inst)) {
      order.push(inst);
      map.set(inst, []);
    }
    map.get(inst)!.push(a);
  }
  return order.map((institution) => ({
    institution,
    accounts: (map.get(institution) || []).slice().sort((a, b) =>
      accountSubKey(a).localeCompare(accountSubKey(b), "ko")
    ),
  }));
}

export function subsForInstitution(
  accounts: AccountRow[],
  institution: string,
  ownership?: string | null
): Array<{ key: string; label: string }> {
  const own =
    ownership && ["joint", "mine", "spouse"].includes(ownership)
      ? ownership
      : null;
  const seen = new Map<string, string>();
  for (const a of accounts) {
    if ((a.institution || "계좌") !== institution) continue;
    if (own && (a.ownership || "joint") !== own) continue;
    const key = accountSubKey(a);
    if (!seen.has(key)) seen.set(key, accountSubLabel(a));
  }
  return [...seen.entries()]
    .map(([key, label]) => ({ key, label }))
    .sort((a, b) => a.key.localeCompare(b.key, "ko"));
}

export function accountIdsForInstitution(
  accounts: AccountRow[],
  institution: string | null | undefined,
  sub?: string | null
): string[] | null {
  if (!institution || institution === "전체") return null;
  let rows = accounts.filter((a) => (a.institution || "계좌") === institution);
  if (sub && sub !== "전체") {
    rows = rows.filter((a) => accountSubKey(a) === sub || a.id === sub);
  }
  return rows.map((a) => a.id);
}

export function computeNetWorth(args: {
  live: LiveHolding[];
  accounts: AccountRow[];
  otherAssets: OtherAssetRow[];
  totalDebt: number;
  usdkrw: number | null;
  accountIds?: string[] | null;
  ownership?: string | null;
}): NetWorth {
  const {
    live,
    accounts,
    otherAssets,
    totalDebt,
    usdkrw,
    accountIds = null,
    ownership = null,
  } = args;
  const allow = accountIds ? new Set(accountIds.map(String)) : null;
  const own =
    ownership && ["joint", "mine", "spouse"].includes(ownership)
      ? ownership
      : null;
  const amap = new Map(accounts.map((a) => [a.id, a]));

  let invest = 0;
  let domestic = 0;
  let overseas = 0;
  let bankHoldings = 0;

  for (const r of live) {
    if (allow && !allow.has(r.account_id)) continue;
    const acct = amap.get(r.account_id);
    if (own && (acct?.ownership || "joint") !== own) continue;
    const v = r.value_krw || 0;
    const type = acct?.account_type || "brokerage";
    if (type === "bank") {
      bankHoldings += v;
      continue;
    }
    if (type === "loan") continue;
    invest += v;
    if (r.region === "국내") domestic += v;
    else overseas += v;
  }

  let cash = bankHoldings;
  for (const a of accounts) {
    if (allow && !allow.has(a.id)) continue;
    if (own && (a.ownership || "joint") !== own) continue;
    const bal = Number(a.cash_balance || 0);
    cash += toKrw(bal, a.currency || "KRW", usdkrw);
  }

  let other = 0;
  const other_rows: OtherAssetRow[] = [];
  // Account filter = account lens → omit household other assets
  if (!allow) {
    for (const o of otherAssets) {
      if (own && (o.ownership || "joint") !== own) continue;
      const val = Number(o.value_krw || 0);
      other += val;
      other_rows.push(o);
    }
  }

  let debt = Number(totalDebt || 0);
  if (allow) debt = 0;

  const gross = invest + cash + other;
  return {
    invest,
    cash,
    other,
    debt,
    gross,
    net: gross - debt,
    domestic,
    overseas,
    cash_ratio: gross > 0 ? cash / gross : 0,
    other_rows,
  };
}

export function filterLiveByAccountAndOwnership(
  live: LiveHolding[],
  accounts: AccountRow[],
  accountIds: string[] | null,
  ownership: string | null
): LiveHolding[] {
  const allow = accountIds ? new Set(accountIds.map(String)) : null;
  const own =
    ownership && ["joint", "mine", "spouse"].includes(ownership)
      ? ownership
      : null;
  const amap = new Map(accounts.map((a) => [a.id, a]));
  return live.filter((r) => {
    if (allow && !allow.has(r.account_id)) return false;
    if (own) {
      const a = amap.get(r.account_id);
      if ((a?.ownership || "joint") !== own) return false;
    }
    return true;
  });
}

export function monthlySummaryStats(args: {
  liveNet: number | null;
  snaps: DailySnap[];
  realizedMonth: number | null;
  now?: Date;
}): MonthlySummary {
  const now = args.now || new Date();
  const monthStartIso = monthStartKst(now);

  const out: MonthlySummary = {
    month_start: monthStartIso,
    nw_start: null,
    nw_now: args.liveNet,
    nw_change: null,
    nw_change_pct: null,
    realized_month: args.realizedMonth,
  };

  const prior = args.snaps
    .filter((s) => String(s.snapshot_date || "") <= monthStartIso)
    .sort((a, b) => String(a.snapshot_date).localeCompare(String(b.snapshot_date)));
  if (prior.length) {
    const last = prior[prior.length - 1];
    const v = Number(last.net_assets);
    out.nw_start = Number.isFinite(v) ? v : null;
  }

  if (out.nw_start != null && args.liveNet != null) {
    out.nw_change = args.liveNet - out.nw_start;
    if (Math.abs(out.nw_start) > 1) {
      out.nw_change_pct = (100 * out.nw_change) / out.nw_start;
    }
  }

  return out;
}

export function debtsDueSoon(
  debts: DebtRow[],
  withinDays = 45,
  now = new Date()
): Array<DebtRow & { days: number; due: string }> {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(today);
  end.setDate(end.getDate() + withinDays);
  const out: Array<DebtRow & { days: number; due: string }> = [];
  for (const d of debts) {
    if (!d.due_date) continue;
    const due = new Date(String(d.due_date).slice(0, 10) + "T00:00:00");
    if (Number.isNaN(due.getTime())) continue;
    if (due >= today && due <= end) {
      const days = Math.round(
        (due.getTime() - today.getTime()) / (24 * 60 * 60 * 1000)
      );
      out.push({ ...d, days, due: String(d.due_date).slice(0, 10) });
    }
  }
  return out.sort((a, b) => a.due.localeCompare(b.due));
}

export function otherAssetReturn(row: Pick<OtherAssetRow, "value_krw" | "cost_krw">): {
  cost: number | null;
  value: number;
  pnl: number | null;
  pct: number | null;
} {
  const value = Number(row.value_krw || 0);
  const costRaw = Number(row.cost_krw);
  const cost = Number.isFinite(costRaw) && costRaw > 0 ? costRaw : null;
  if (cost === null) {
    return { cost: null, value, pnl: null, pct: null };
  }
  const pnl = value - cost;
  return { cost, value, pnl, pct: (100 * pnl) / cost };
}

export function groupOtherByKind(rows: OtherAssetRow[]) {
  const map = new Map<string, number>();
  for (const r of rows) {
    const k = r.asset_kind || "other";
    map.set(k, (map.get(k) || 0) + Number(r.value_krw || 0));
  }
  const total = [...map.values()].reduce((s, v) => s + v, 0);
  return [...map.entries()]
    .map(([kind, value]) => ({
      kind,
      label: ASSET_KIND_KO[kind] || kind,
      value,
      pct: total > 0 ? (100 * value) / total : 0,
    }))
    .sort((a, b) => b.value - a.value);
}

export function institutionsForOwnership(
  accounts: Array<Pick<AccountRow, "institution" | "ownership">>,
  ownership?: string | null
): string[] {
  const own =
    ownership && ["joint", "mine", "spouse"].includes(ownership)
      ? ownership
      : null;
  const set = new Set<string>();
  for (const a of accounts) {
    if (own && (a.ownership || "joint") !== own) continue;
    set.add(a.institution || "계좌");
  }
  return [...set].sort((a, b) => a.localeCompare(b, "ko"));
}

export function institutionsFromAccounts(accounts: AccountRow[]): string[] {
  return institutionsForOwnership(accounts, null);
}

export function filterQuery(sp: {
  own?: string | null;
  inst?: string | null;
  sub?: string | null;
}): string {
  return [
    sp.own ? `own=${encodeURIComponent(sp.own)}` : "",
    sp.inst ? `inst=${encodeURIComponent(sp.inst)}` : "",
    sp.sub ? `sub=${encodeURIComponent(sp.sub)}` : "",
  ]
    .filter(Boolean)
    .join("&");
}
