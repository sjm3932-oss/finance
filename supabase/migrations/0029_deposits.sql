-- Dedicated 예적금 (time deposits / installment savings).
-- Not accounts.cash_balance (증권 예수금, API-synced) and not other_assets.

create table if not exists public.deposits (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  institution text not null,
  name text not null,
  deposit_kind text not null default 'time'
    check (deposit_kind in (
      'demand', 'time', 'installment', 'subscription', 'cma', 'other'
    )),
  principal numeric not null default 0,
  current_value numeric not null default 0,
  interest_rate numeric not null default 0,
  start_date date,
  maturity_date date,
  ownership text not null default 'joint'
    check (ownership in ('joint', 'mine', 'spouse')),
  memo text,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

comment on table public.deposits is '예적금: 원금·이율·만기. 증권 예수금(accounts.cash_balance)과 별도.';
comment on column public.deposits.principal is '가입 원금';
comment on column public.deposits.current_value is '현재 평가액(이자 포함). 0이면 principal 사용';
comment on column public.deposits.interest_rate is '연 이자율 (%)';
comment on column public.deposits.maturity_date is '만기일 (입출금은 null 가능)';

create index if not exists idx_deposits_user on public.deposits(user_id);
create index if not exists idx_deposits_maturity
  on public.deposits(maturity_date)
  where maturity_date is not null;

alter table public.deposits enable row level security;

drop policy if exists couple_all_deposits on public.deposits;
create policy couple_all_deposits on public.deposits
  for all to authenticated
  using (public.is_couple_member())
  with check (
    public.is_couple_member()
    and user_id in (select id from public.users)
  );

grant select, insert, update, delete on public.deposits to authenticated;
grant select, insert, update, delete on public.deposits to service_role;

-- Move leftover other_assets.deposit rows so they are not double-counted.
insert into public.deposits (
  user_id, institution, name, deposit_kind,
  principal, current_value, interest_rate, ownership, memo, updated_at, created_at
)
select
  o.user_id,
  '기타',
  o.name,
  'time',
  coalesce(o.value_krw, 0),
  coalesce(o.value_krw, 0),
  0,
  o.ownership,
  o.memo,
  o.updated_at,
  o.created_at
from public.other_assets o
where o.asset_kind = 'deposit';

delete from public.other_assets where asset_kind = 'deposit';

-- Snapshot column
alter table public.daily_snapshots
  add column if not exists total_deposits numeric not null default 0;

-- Allocation: 예적금 as its own bucket (existing 40/40/15/5 stay; deposits starts at 0)
alter table public.allocation_targets
  drop constraint if exists allocation_targets_category_check;

alter table public.allocation_targets
  add constraint allocation_targets_category_check
  check (category in ('domestic', 'overseas', 'cash', 'deposits', 'other'));

insert into public.allocation_targets (category, target_pct) values
  ('deposits', 0)
on conflict (category) do nothing;

-- ---------------------------------------------------------------------------
-- Recompute daily snapshot: invest + cash + deposits + other − debt
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
  v_deposits numeric := 0;
  v_bank numeric := 0;
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

  -- Cash = 증권 예수금 (API-synced cash_balance) + bank holdings
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
  into v_bank
  from public.holdings h
  join public.accounts a on a.id = h.account_id
  left join public.market_prices mp on mp.ticker = h.ticker
  where a.account_type = 'bank';

  v_cash := v_cash + coalesce(v_bank, 0);

  select coalesce(sum(
    case
      when coalesce(current_value, 0) > 0 then current_value
      else coalesce(principal, 0)
    end
  ), 0)
  into v_deposits
  from public.deposits;

  select coalesce(sum(value_krw), 0)
  into v_other
  from public.other_assets
  where coalesce(asset_kind, '') is distinct from 'deposit';

  select coalesce(sum(principal), 0) into v_debt from public.debts;

  v_gross := v_invest + v_cash + v_deposits + v_other;
  v_net := v_gross - v_debt;
  if v_gross > 0 then
    v_cash_ratio := v_cash / v_gross;
  else
    v_cash_ratio := 0;
  end if;

  insert into public.daily_snapshots as ds (
    snapshot_date, net_assets, total_investment, total_debt, cash_ratio,
    total_cash, total_other, total_deposits
  ) values (
    v_date, v_net, v_invest, v_debt, v_cash_ratio, v_cash, v_other, v_deposits
  )
  on conflict (snapshot_date) do update
  set
    net_assets = excluded.net_assets,
    total_investment = excluded.total_investment,
    total_debt = excluded.total_debt,
    cash_ratio = excluded.cash_ratio,
    total_cash = excluded.total_cash,
    total_other = excluded.total_other,
    total_deposits = excluded.total_deposits
  returning * into v_row;

  return v_row;
end;
$$;

revoke all on function public.compute_daily_snapshot(date) from public;
grant execute on function public.compute_daily_snapshot(date) to authenticated;
grant execute on function public.compute_daily_snapshot(date) to service_role;
