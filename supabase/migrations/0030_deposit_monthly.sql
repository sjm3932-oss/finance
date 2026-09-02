-- 적금/청약: 월 납입액. Live value is computed from start_date + monthly_amount + rate.

alter table public.deposits
  add column if not exists monthly_amount numeric not null default 0;

comment on column public.deposits.monthly_amount is '적금·청약 월 납입액. 0이면 일시예치(원금/현재잔액) 사용';

create or replace function public.calendar_months_between(p_from date, p_to date)
returns integer
language sql
immutable
as $$
  select case
    when p_from is null or p_to is null or p_to < p_from then 0
    else greatest(
      0,
      (extract(year from p_to)::int - extract(year from p_from)::int) * 12
      + (extract(month from p_to)::int - extract(month from p_from)::int)
      - case when extract(day from p_to) < extract(day from p_from) then 1 else 0 end
    )
  end;
$$;

create or replace function public.deposit_eval_krw(
  p_kind text,
  p_principal numeric,
  p_current numeric,
  p_monthly numeric,
  p_rate numeric,
  p_start date,
  p_maturity date,
  p_asof date default (timezone('Asia/Seoul', now()))::date
)
returns numeric
language plpgsql
immutable
as $$
declare
  v_monthly numeric := coalesce(p_monthly, 0);
  v_total int := 0;
  v_made int := 0;
  v_rate numeric := coalesce(p_rate, 0) / 100.0;
  v_until date;
begin
  if p_kind in ('installment', 'subscription')
     and v_monthly > 0
     and p_start is not null then
    if p_maturity is not null then
      v_total := greatest(1, public.calendar_months_between(p_start, p_maturity));
    else
      v_total := 1200;
    end if;
    if p_asof < p_start then
      return 0;
    end if;
    v_until := p_asof;
    if p_maturity is not null and p_maturity < p_asof then
      v_until := p_maturity;
    end if;
    v_made := least(
      v_total,
      public.calendar_months_between(p_start, v_until) + 1
    );
    v_made := greatest(v_made, 0);
    return v_monthly * v_made
      + round(v_monthly * (v_rate / 12.0) * v_made * greatest(v_made - 1, 0) / 2.0);
  end if;
  if coalesce(p_current, 0) > 0 then
    return p_current;
  end if;
  return coalesce(p_principal, 0);
end;
$$;

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
    public.deposit_eval_krw(
      deposit_kind, principal, current_value, monthly_amount,
      interest_rate, start_date, maturity_date, v_date
    )
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
grant execute on function public.calendar_months_between(date, date) to authenticated;
grant execute on function public.deposit_eval_krw(text, numeric, numeric, numeric, numeric, date, date, date) to authenticated;
