-- 적금/청약: 이미 넣고 있는 상품의 은행 잔액. 기준일 이후 월납은 계속 자동 가산.

alter table public.deposits
  add column if not exists balance_as_of date;

comment on column public.deposits.current_value is
  '현재 평가액. 적금·청약은 0이면 가입일부터 월납 자동계산, >0이면 이 금액을 balance_as_of 기준으로 쓰고 이후 월납을 더함';
comment on column public.deposits.balance_as_of is
  '적금·청약 current_value가 맞는 날짜. 이후 납입 회차만큼 월납을 가산';

drop function if exists public.deposit_eval_krw(text, numeric, numeric, numeric, numeric, date, date, date);

create or replace function public.deposit_eval_krw(
  p_kind text,
  p_principal numeric,
  p_current numeric,
  p_monthly numeric,
  p_rate numeric,
  p_start date,
  p_maturity date,
  p_asof date default (timezone('Asia/Seoul', now()))::date,
  p_balance_asof date default null
)
returns numeric
language plpgsql
immutable
as $$
declare
  v_monthly numeric := coalesce(p_monthly, 0);
  v_total int := 0;
  v_made int := 0;
  v_made_then int := 0;
  v_extra int := 0;
  v_rate numeric := coalesce(p_rate, 0) / 100.0;
  v_until date;
  v_seed numeric := coalesce(p_current, 0);
  v_seed_on date;
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

    if v_seed > 0 then
      v_seed_on := coalesce(p_balance_asof, p_asof);
      if p_asof < v_seed_on then
        return v_monthly * v_made
          + round(v_monthly * (v_rate / 12.0) * v_made * greatest(v_made - 1, 0) / 2.0);
      end if;
      v_until := v_seed_on;
      if p_maturity is not null and p_maturity < v_seed_on then
        v_until := p_maturity;
      end if;
      if v_seed_on < p_start then
        v_made_then := 0;
      else
        v_made_then := least(
          v_total,
          public.calendar_months_between(p_start, v_until) + 1
        );
      end if;
      v_extra := greatest(0, v_made - v_made_then);
      return v_seed
        + v_monthly * v_extra
        + round(v_monthly * (v_rate / 12.0) * v_extra * greatest(v_extra - 1, 0) / 2.0);
    end if;

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
      interest_rate, start_date, maturity_date, v_date, balance_as_of
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
grant execute on function public.deposit_eval_krw(text, numeric, numeric, numeric, numeric, date, date, date, date) to authenticated;
