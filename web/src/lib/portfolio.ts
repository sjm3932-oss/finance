import { marketRegion } from "@/lib/money";

export type AccountRow = {
  id: string;
  institution: string | null;
  account_type: string | null;
  currency: string | null;
  ownership?: string | null;
  cash_balance?: number | null;
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
    const price = mp?.price ?? null;
    const qty = Number(h.quantity || 0);
    const avg = Number(h.avg_price || 0);
    const ccy = (h.currency || mp?.currency || "USD").toUpperCase();
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
      institution: acct?.institution || "계좌",
      qty,
      avg,
      price,
      value,
      value_krw,
      cost_krw,
      return_pct,
      ccy,
      region: marketRegion(h.ticker, ccy),
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
    const ccy = list[0]?.ccy || "USD";
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

export function computeNetWorth(args: {
  live: LiveHolding[];
  accounts: AccountRow[];
  otherAssets: { value_krw?: number | null; ownership?: string | null }[];
  totalDebt: number;
  usdkrw: number | null;
}): NetWorth {
  const { live, accounts, otherAssets, totalDebt, usdkrw } = args;
  const amap = new Map(accounts.map((a) => [a.id, a]));

  let invest = 0;
  let domestic = 0;
  let overseas = 0;
  let bankHoldings = 0;

  for (const r of live) {
    const acct = amap.get(r.account_id);
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
    const bal = Number(a.cash_balance || 0);
    cash += toKrw(bal, a.currency || "KRW", usdkrw);
  }

  const other = otherAssets.reduce(
    (s, o) => s + Number(o.value_krw || 0),
    0
  );
  const debt = Number(totalDebt || 0);
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
  };
}
