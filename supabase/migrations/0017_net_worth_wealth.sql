-- 0017_net_worth_wealth.sql
-- Comprehensive wealth: cash balances, other assets, ownership tags,
-- allocation targets, richer daily snapshots.

-- ---------------------------------------------------------------------------
-- Accounts: ownership + cash balance (account currency)
-- ---------------------------------------------------------------------------
alter table public.accounts
  add column if not exists ownership text not null default 'joint';

alter table public.accounts
  add column if not exists cash_balance numeric not null default 0;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'accounts_ownership_check'
  ) then
    alter table public.accounts
      add constraint accounts_ownership_check
      check (ownership in ('joint', 'mine', 'spouse'));
  end if;
end $$;

comment on column public.accounts.ownership is 'joint | mine | spouse';
comment on column public.accounts.cash_balance is 'Cash/예수금 in account.currency';

-- ---------------------------------------------------------------------------
-- Other assets (real estate, pension, etc.)
-- ---------------------------------------------------------------------------
create table if not exists public.other_assets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  name text not null,
  asset_kind text not null
    check (asset_kind in (
      'real_estate', 'pension', 'insurance', 'deposit', 'crypto', 'other'
    )),
  value_krw numeric not null default 0,
  ownership text not null default 'joint'
    check (ownership in ('joint', 'mine', 'spouse')),
  memo text,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists idx_other_assets_user on public.other_assets(user_id);

alter table public.other_assets enable row level security;

drop policy if exists couple_all_other_assets on public.other_assets;
create policy couple_all_other_assets on public.other_assets
  for all to authenticated
  using (public.is_couple_member())
  with check (
    public.is_couple_member()
    and user_id in (select id from public.users)
  );

-- ---------------------------------------------------------------------------
-- Allocation targets (% of gross assets: invest+cash+other)
-- ---------------------------------------------------------------------------
create table if not exists public.allocation_targets (
  category text primary key
    check (category in ('domestic', 'overseas', 'cash', 'other')),
  target_pct numeric not null default 0
    check (target_pct >= 0 and target_pct <= 100),
  updated_at timestamptz not null default now()
);

alter table public.allocation_targets enable row level security;

drop policy if exists couple_all_allocation_targets on public.allocation_targets;
create policy couple_all_allocation_targets on public.allocation_targets
  for all to authenticated
  using (public.is_couple_member())
  with check (public.is_couple_member());

insert into public.allocation_targets (category, target_pct) values
  ('domestic', 40),
  ('overseas', 40),
  ('cash', 15),
  ('other', 5)
on conflict (category) do nothing;

-- ---------------------------------------------------------------------------
-- Debts: ownership tag (optional filtering)
-- ---------------------------------------------------------------------------
alter table public.debts
  add column if not exists ownership text not null default 'joint';

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'debts_ownership_check'
  ) then
    alter table public.debts
      add constraint debts_ownership_check
      check (ownership in ('joint', 'mine', 'spouse'));
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- Daily snapshots: cash + other
-- ---------------------------------------------------------------------------
alter table public.daily_snapshots
  add column if not exists total_cash numeric not null default 0;

alter table public.daily_snapshots
  add column if not exists total_other numeric not null default 0;

-- ---------------------------------------------------------------------------
-- Wealth alert events (NW drop, debt due, monthly digest)
-- ---------------------------------------------------------------------------
create table if not exists public.wealth_alert_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  alert_kind text not null
    check (alert_kind in ('nw_drop', 'debt_due', 'monthly_digest', 'stale_prices')),
  title text not null,
  body text,
  meta jsonb not null default '{}'::jsonb,
  acknowledged boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists idx_wealth_alerts_user
  on public.wealth_alert_events(user_id, acknowledged, created_at desc);

alter table public.wealth_alert_events enable row level security;

drop policy if exists couple_all_wealth_alerts on public.wealth_alert_events;
create policy couple_all_wealth_alerts on public.wealth_alert_events
  for all to authenticated
  using (public.is_couple_member())
  with check (
    public.is_couple_member()
    and user_id in (select id from public.users)
  );

-- ---------------------------------------------------------------------------
-- Recompute daily snapshot with cash + other assets
-- ---------------------------------------------------------------------------
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
  v_other numeric := 0;
  v_net numeric := 0;
  v_cash_ratio numeric := 0;
  v_usdkrw numeric := 1;
  v_row public.daily_snapshots;
  v_date date := coalesce(p_date, (timezone('Asia/Seoul', now()))::date);
  v_gross numeric := 0;
begin
  select coalesce(
    (select price from public.market_prices where ticker = 'USDKRW' limit 1),
    1
  ) into v_usdkrw;

  -- Brokerage investment market value (exclude bank account holdings)
  select coalesce(sum(
    case
      when coalesce(h.currency, 'KRW') = 'USD'
        then h.quantity * coalesce(mp.price, h.avg_price, 0) * v_usdkrw
      else h.quantity * coalesce(mp.price, h.avg_price, 0)
    end
  ), 0)
  into v_invest
  from public.holdings h
  join public.accounts a on a.id = h.account_id
  left join public.market_prices mp on mp.ticker = h.ticker
  where a.account_type = 'brokerage';

  -- Cash: account.cash_balance + bank holdings
  select coalesce(sum(
    case
      when coalesce(a.currency, 'KRW') = 'USD' then coalesce(a.cash_balance, 0) * v_usdkrw
      else coalesce(a.cash_balance, 0)
    end
  ), 0)
  into v_cash
  from public.accounts a;

  select coalesce(sum(
    case
      when coalesce(h.currency, 'KRW') = 'USD'
        then h.quantity * coalesce(mp.price, 1) * v_usdkrw
      else h.quantity * coalesce(mp.price, 1)
    end
  ), 0)
  into v_other  -- temp reuse; reassigned below for bank holdings add-on
  from public.holdings h
  join public.accounts a on a.id = h.account_id
  left join public.market_prices mp on mp.ticker = h.ticker
  where a.account_type = 'bank';

  v_cash := v_cash + coalesce(v_other, 0);

  select coalesce(sum(value_krw), 0) into v_other from public.other_assets;

  select coalesce(sum(principal), 0) into v_debt from public.debts;

  v_net := v_invest + v_cash + v_other - v_debt;
  v_gross := v_invest + v_cash + v_other;
  if v_gross > 0 then
    v_cash_ratio := v_cash / v_gross;
  else
    v_cash_ratio := 0;
  end if;

  insert into public.daily_snapshots as ds (
    snapshot_date, net_assets, total_investment, total_debt, cash_ratio,
    total_cash, total_other
  ) values (
    v_date, v_net, v_invest, v_debt, v_cash_ratio, v_cash, v_other
  )
  on conflict (snapshot_date) do update
  set
    net_assets = excluded.net_assets,
    total_investment = excluded.total_investment,
    total_debt = excluded.total_debt,
    cash_ratio = excluded.cash_ratio,
    total_cash = excluded.total_cash,
    total_other = excluded.total_other
  returning * into v_row;

  return v_row;
end;
$$;

revoke all on function public.compute_daily_snapshot(date) from public;
grant execute on function public.compute_daily_snapshot(date) to authenticated;
grant execute on function public.compute_daily_snapshot(date) to service_role;

grant select, insert, update, delete on public.other_assets to authenticated;
grant select, insert, update, delete on public.allocation_targets to authenticated;
grant select, insert, update, delete on public.wealth_alert_events to authenticated;
