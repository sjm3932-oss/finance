-- 0011_total_realized_pnl.sql
-- Combined realized P&L from sells, dividends, interest income, and debt interest cost.

create or replace view public.v_total_realized_pnl as
-- 1) Sell trades — capital gains / losses already stored on the row
select
  t.trade_date as event_date,
  'trade_realized'::text as pnl_kind,
  t.ticker as asset_ref,
  t.realized_pnl as pnl,
  coalesce(t.currency, 'USD') as currency,
  t.id as source_id,
  'trades'::text as source_table,
  t.created_by as user_id
from public.trades t
where t.trade_type = 'sell'
  and t.realized_pnl is not null

union all

-- 2) Dividends — cash received counts as realized income
select
  d.pay_date,
  'dividend',
  d.ticker,
  d.amount,
  coalesce(d.currency, 'USD'),
  d.id,
  'dividends',
  d.user_id
from public.dividends d
where d.amount is not null

union all

-- 3) Interest income (cash_flows categorized as 이자)
select
  c.flow_date,
  'interest_income',
  coalesce(c.category, '이자'),
  c.amount,
  coalesce(c.currency, 'KRW'),
  c.id,
  'cash_flows',
  c.user_id
from public.cash_flows c
where c.flow_type = 'income'
  and (
    c.category ilike '%이자%'
    or c.category ilike '%interest%'
  )

union all

-- 4) Debt interest — financing cost (negative contribution to realized P&L)
select
  dt.tx_date,
  'interest_expense',
  dk.lender,
  -abs(dt.amount),
  'KRW',
  dt.id,
  'debt_transactions',
  dt.user_id
from public.debt_transactions dt
join public.debts dk on dk.id = dt.debt_id
where dt.tx_type = 'interest';

grant select on public.v_total_realized_pnl to authenticated;

comment on view public.v_total_realized_pnl is
  'Combined realized P&L: sell gains, dividends, interest income, debt interest cost';
