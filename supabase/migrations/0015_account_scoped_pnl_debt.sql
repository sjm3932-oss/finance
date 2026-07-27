-- 0015_account_scoped_pnl_debt.sql
-- Add account_id on debts; expose account_id on realized PnL view;
-- fix debt rows in v_asset_flows to use debts.account_id.

alter table public.debts
  add column if not exists account_id uuid references public.accounts(id) on delete set null;

create index if not exists idx_debts_account_id on public.debts(account_id);

comment on column public.debts.account_id is
  'Optional link to brokerage/bank account for dashboard filtering.';

create or replace view public.v_total_realized_pnl as
select
  t.trade_date as event_date,
  'trade_realized'::text as pnl_kind,
  t.ticker as asset_ref,
  t.ticker as asset_name,
  t.realized_pnl as pnl,
  coalesce(t.currency, 'USD') as currency,
  t.id as source_id,
  'trades'::text as source_table,
  t.created_by as user_id,
  t.account_id::text as account_id
from public.trades t
where t.trade_type = 'sell'
  and t.realized_pnl is not null

union all

select
  d.pay_date,
  'dividend',
  d.ticker,
  coalesce(nullif(d.name, ''), d.ticker),
  d.amount,
  coalesce(d.currency, 'USD'),
  d.id,
  'dividends',
  d.user_id,
  d.account_id::text
from public.dividends d
where d.amount is not null

union all

select
  c.flow_date,
  'interest_income',
  coalesce(c.category, '이자'),
  coalesce(c.category, '이자'),
  c.amount,
  coalesce(c.currency, 'KRW'),
  c.id,
  'cash_flows',
  c.user_id,
  c.account_id::text
from public.cash_flows c
where c.flow_type = 'income'
  and (
    c.category ilike '%이자%'
    or c.category ilike '%interest%'
  )

union all

select
  dt.tx_date,
  'interest_expense',
  dk.lender,
  dk.lender,
  -abs(coalesce(dt.interest_portion, dt.amount)),
  'KRW',
  dt.id,
  'debt_transactions',
  dt.user_id,
  dk.account_id::text
from public.debt_transactions dt
join public.debts dk on dk.id = dt.debt_id
where dt.tx_type = 'interest';

grant select on public.v_total_realized_pnl to authenticated;

create or replace view public.v_asset_flows as
select
  t.created_at as recorded_at,
  t.trade_date as event_date,
  'trade'::text as flow_kind,
  t.trade_type as flow_subtype,
  t.ticker as asset_ref,
  case when t.trade_type = 'buy' then - (t.price * t.quantity + coalesce(t.fee,0))
       else (t.price * t.quantity - coalesce(t.fee,0)) end as amount,
  coalesce(t.currency, 'KRW') as currency,
  t.realized_pnl,
  t.reason as memo,
  t.account_id::text as account_id,
  t.created_by as user_id,
  t.id as source_id,
  'trades'::text as source_table
from public.trades t

union all

select
  d.created_at,
  d.pay_date,
  'dividend',
  'dividend',
  d.ticker,
  d.amount,
  d.currency,
  null,
  d.memo,
  d.account_id::text,
  d.user_id,
  d.id,
  'dividends'
from public.dividends d

union all

select
  c.created_at,
  c.flow_date,
  'cash_flow',
  c.flow_type || ':' || c.category,
  c.category,
  case when c.flow_type = 'expense' then -c.amount else c.amount end,
  coalesce(c.currency, 'KRW'),
  null,
  c.memo,
  c.account_id::text,
  c.user_id,
  c.id,
  'cash_flows'
from public.cash_flows c

union all

select
  dt.created_at,
  dt.tx_date,
  'debt',
  dt.tx_type,
  dk.lender,
  case when dt.tx_type in ('increase', 'interest') then dt.amount
       when dt.tx_type in ('decrease', 'repayment') then -dt.amount
       else dt.amount end,
  'KRW',
  null,
  dt.memo,
  dk.account_id::text,
  dt.user_id,
  dt.id,
  'debt_transactions'
from public.debt_transactions dt
join public.debts dk on dk.id = dt.debt_id;

grant select on public.v_asset_flows to authenticated;
