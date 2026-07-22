-- 0008_holding_daily_snapshots.sql
-- Per-asset daily snapshots + extend compute_daily_snapshot()

create table if not exists public.holding_daily_snapshots (
  id uuid primary key default gen_random_uuid(),
  snapshot_date date not null,
  account_id uuid not null references public.accounts(id) on delete cascade,
  ticker text not null,
  name text,
  quantity numeric not null default 0,
  avg_price numeric not null default 0,
  price numeric,
  currency text not null default 'KRW',
  market_value numeric,
  market_value_krw numeric,
  return_rate numeric,
  usdkrw numeric,
  created_at timestamptz not null default now(),
  unique (snapshot_date, account_id, ticker)
);

create index if not exists idx_holding_daily_snapshots_date
  on public.holding_daily_snapshots(snapshot_date);
create index if not exists idx_holding_daily_snapshots_ticker
  on public.holding_daily_snapshots(ticker);
create index if not exists idx_holding_daily_snapshots_date_ticker
  on public.holding_daily_snapshots(snapshot_date, ticker);

alter table public.holding_daily_snapshots enable row level security;

drop policy if exists couple_all_holding_daily_snapshots on public.holding_daily_snapshots;
create policy couple_all_holding_daily_snapshots on public.holding_daily_snapshots
  for all to authenticated
  using (public.is_couple_member())
  with check (public.is_couple_member());

grant select, insert, update, delete on public.holding_daily_snapshots to authenticated;

-- Rebuild aggregate + per-holding snapshot for a KST calendar day
create or replace function public.compute_daily_snapshot(
  p_date date default (timezone('Asia/Seoul', now()))::date
)
returns public.daily_snapshots
language plpgsql
security definer
set search_path = public
as $$
declare
  v_invest numeric := 0;
  v_debt numeric := 0;
  v_cash numeric := 0;
  v_net numeric := 0;
  v_cash_ratio numeric := 0;
  v_usdkrw numeric := 1;
  v_row public.daily_snapshots;
  v_date date := coalesce(p_date, (timezone('Asia/Seoul', now()))::date);
begin
  select coalesce(
    (select price from public.market_prices where ticker = 'USDKRW' limit 1),
    1
  ) into v_usdkrw;

  -- Upsert one row per holding for the day
  insert into public.holding_daily_snapshots as hds (
    snapshot_date,
    account_id,
    ticker,
    name,
    quantity,
    avg_price,
    price,
    currency,
    market_value,
    market_value_krw,
    return_rate,
    usdkrw
  )
  select
    v_date,
    h.account_id,
    h.ticker,
    h.name,
    h.quantity,
    h.avg_price,
    mp.price,
    coalesce(h.currency, mp.currency, 'KRW'),
    case when mp.price is null then null else h.quantity * mp.price end,
    case
      when mp.price is null then null
      when coalesce(h.currency, mp.currency, 'KRW') = 'USD' then h.quantity * mp.price * v_usdkrw
      else h.quantity * mp.price
    end,
    case
      when mp.price is null or nullif(h.avg_price, 0) is null then null
      else (mp.price - h.avg_price) / h.avg_price * 100
    end,
    v_usdkrw
  from public.holdings h
  left join public.market_prices mp on mp.ticker = h.ticker
  on conflict (snapshot_date, account_id, ticker) do update
  set
    name = excluded.name,
    quantity = excluded.quantity,
    avg_price = excluded.avg_price,
    price = excluded.price,
    currency = excluded.currency,
    market_value = excluded.market_value,
    market_value_krw = excluded.market_value_krw,
    return_rate = excluded.return_rate,
    usdkrw = excluded.usdkrw;

  select coalesce(sum(market_value_krw), 0)
  into v_invest
  from public.holding_daily_snapshots
  where snapshot_date = v_date
    and market_value_krw is not null;

  -- Fallback if all prices missing: cost basis style estimate
  if v_invest = 0 then
    select coalesce(sum(
      case
        when coalesce(h.currency, 'KRW') = 'USD' then h.quantity * coalesce(h.avg_price, 0) * v_usdkrw
        else h.quantity * coalesce(h.avg_price, 0)
      end
    ), 0)
    into v_invest
    from public.holdings h;
  end if;

  select coalesce(sum(principal), 0) into v_debt from public.debts;

  select coalesce(sum(hds.market_value_krw), 0)
  into v_cash
  from public.holding_daily_snapshots hds
  join public.accounts a on a.id = hds.account_id
  where hds.snapshot_date = v_date
    and a.account_type = 'bank'
    and hds.market_value_krw is not null;

  v_net := v_invest - v_debt;
  if v_invest > 0 then
    v_cash_ratio := v_cash / v_invest;
  else
    v_cash_ratio := 0;
  end if;

  insert into public.daily_snapshots as ds (
    snapshot_date, net_assets, total_investment, total_debt, cash_ratio
  ) values (
    v_date, v_net, v_invest, v_debt, v_cash_ratio
  )
  on conflict (snapshot_date) do update
  set
    net_assets = excluded.net_assets,
    total_investment = excluded.total_investment,
    total_debt = excluded.total_debt,
    cash_ratio = excluded.cash_ratio
  returning * into v_row;

  return v_row;
end;
$$;

revoke all on function public.compute_daily_snapshot(date) from public;
grant execute on function public.compute_daily_snapshot(date) to authenticated;
grant execute on function public.compute_daily_snapshot(date) to service_role;

-- Convenience: list distinct snapshot dates
create or replace view public.v_holding_snapshot_dates as
select distinct snapshot_date
from public.holding_daily_snapshots
order by snapshot_date desc;

grant select on public.v_holding_snapshot_dates to authenticated;
