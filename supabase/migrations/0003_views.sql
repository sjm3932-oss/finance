-- 0003_views.sql — Derived portfolio and tax views

create or replace view public.v_portfolio as
select
  h.account_id,
  h.ticker,
  h.name,
  h.quantity,
  h.avg_price,
  mp.price as current_price,
  (mp.price - h.avg_price) / nullif(h.avg_price, 0) * 100 as return_rate,
  h.quantity * mp.price as market_value
from public.holdings h
left join public.market_prices mp on mp.ticker = h.ticker;

create or replace view public.v_tax_calculation as
select
  user_id,
  tax_year,
  greatest(cum_capital_gain - tax_threshold, 0) as taxable_gain,
  greatest(cum_capital_gain - tax_threshold, 0) * 0.22 as estimated_tax
from public.tax_records;

grant select on public.v_portfolio to authenticated;
grant select on public.v_tax_calculation to authenticated;
