-- 0009_asset_flows.sql
-- Full asset-flow ledger: dividends, debt txs, richer cash_flows/trades, unified views

-- ---- Extend cash_flows ----
alter table public.cash_flows
  add column if not exists currency text not null default 'KRW',
  add column if not exists account_id uuid references public.accounts(id) on delete set null;

-- ---- Extend trades ----
alter table public.trades
  add column if not exists fee numeric not null default 0,
  add column if not exists currency text not null default 'KRW',
  add column if not exists realized_pnl numeric,
  add column if not exists memo text,
  add column if not exists adjust_holdings boolean not null default true;

-- Allow trade_type to include corporate actions later; keep buy/sell for now
-- (check constraint already on buy|sell)

-- ---- Dividends ----
create table if not exists public.dividends (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  account_id uuid references public.accounts(id) on delete set null,
  ticker text not null,
  name text,
  pay_date date not null,
  amount numeric not null,
  currency text not null default 'KRW',
  memo text,
  created_at timestamptz not null default now()
);

create index if not exists idx_dividends_pay_date on public.dividends(pay_date desc);
create index if not exists idx_dividends_ticker on public.dividends(ticker);

alter table public.dividends enable row level security;
drop policy if exists couple_all_dividends on public.dividends;
create policy couple_all_dividends on public.dividends
  for all to authenticated
  using (public.is_couple_member())
  with check (
    public.is_couple_member()
    and user_id in (select id from public.users)
  );

grant select, insert, update, delete on public.dividends to authenticated;

-- ---- Debt transactions (increase / decrease / repayment / interest) ----
create table if not exists public.debt_transactions (
  id uuid primary key default gen_random_uuid(),
  debt_id uuid not null references public.debts(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,
  tx_date date not null,
  tx_type text not null check (tx_type in ('increase', 'decrease', 'repayment', 'interest', 'other')),
  amount numeric not null check (amount >= 0),
  memo text,
  created_at timestamptz not null default now()
);

create index if not exists idx_debt_tx_date on public.debt_transactions(tx_date desc);
create index if not exists idx_debt_tx_debt on public.debt_transactions(debt_id);

alter table public.debt_transactions enable row level security;
drop policy if exists couple_all_debt_transactions on public.debt_transactions;
create policy couple_all_debt_transactions on public.debt_transactions
  for all to authenticated
  using (public.is_couple_member())
  with check (
    public.is_couple_member()
    and user_id in (select id from public.users)
  );

grant select, insert, update, delete on public.debt_transactions to authenticated;

-- Apply debt transaction to principal
create or replace function public.apply_debt_transaction()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  delta numeric;
begin
  if tg_op = 'INSERT' then
    delta := case new.tx_type
      when 'increase' then new.amount
      when 'interest' then new.amount  -- capitalize interest into principal by default
      when 'decrease' then -new.amount
      when 'repayment' then -new.amount
      else 0
    end;
    update public.debts
      set principal = greatest(principal + delta, 0)
      where id = new.debt_id;
    return new;
  elsif tg_op = 'DELETE' then
    delta := case old.tx_type
      when 'increase' then -old.amount
      when 'interest' then -old.amount
      when 'decrease' then old.amount
      when 'repayment' then old.amount
      else 0
    end;
    update public.debts
      set principal = greatest(principal + delta, 0)
      where id = old.debt_id;
    return old;
  end if;
  return null;
end;
$$;

drop trigger if exists trg_apply_debt_transaction on public.debt_transactions;
create trigger trg_apply_debt_transaction
  after insert or delete on public.debt_transactions
  for each row execute function public.apply_debt_transaction();

-- ---- Apply buy/sell to holdings + compute realized pnl on sell ----
create or replace function public.apply_trade_to_holdings()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  h public.holdings%rowtype;
  new_qty numeric;
  new_avg numeric;
  pnl numeric;
begin
  if tg_op <> 'INSERT' then
    return new;
  end if;

  if coalesce(new.adjust_holdings, true) is not true then
    return new;
  end if;

  select * into h
  from public.holdings
  where account_id = new.account_id and ticker = new.ticker
  for update;

  if new.trade_type = 'buy' then
    if not found then
      insert into public.holdings (account_id, ticker, name, quantity, avg_price, currency, updated_at)
      values (new.account_id, new.ticker, new.ticker, new.quantity, new.price, coalesce(new.currency, 'KRW'), now());
    else
      new_qty := h.quantity + new.quantity;
      if new_qty > 0 then
        new_avg := (h.quantity * h.avg_price + new.quantity * new.price) / new_qty;
      else
        new_avg := new.price;
      end if;
      update public.holdings
        set quantity = new_qty,
            avg_price = new_avg,
            currency = coalesce(new.currency, h.currency),
            updated_at = now()
        where id = h.id;
    end if;
    new.realized_pnl := coalesce(new.realized_pnl, 0);

  elsif new.trade_type = 'sell' then
    if not found then
      raise exception 'Cannot sell %: no holding in account', new.ticker;
    end if;
    if h.quantity < new.quantity then
      raise exception 'Cannot sell %: qty % > holding %', new.ticker, new.quantity, h.quantity;
    end if;
    pnl := (new.price - h.avg_price) * new.quantity - coalesce(new.fee, 0);
    new.realized_pnl := pnl;
    new_qty := h.quantity - new.quantity;
    if new_qty = 0 then
      delete from public.holdings where id = h.id;
    else
      update public.holdings
        set quantity = new_qty,
            updated_at = now()
        where id = h.id;
    end if;
  end if;

  return new;
end;
$$;

drop trigger if exists trg_apply_trade_to_holdings on public.trades;
create trigger trg_apply_trade_to_holdings
  before insert on public.trades
  for each row execute function public.apply_trade_to_holdings();

-- ---- Unified ledger view ----
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
  dt.debt_id::text,
  dt.user_id,
  dt.id,
  'debt_transactions'
from public.debt_transactions dt
join public.debts dk on dk.id = dt.debt_id;

grant select on public.v_asset_flows to authenticated;

-- Realized PnL summary by ticker/year
create or replace view public.v_realized_pnl as
select
  extract(year from trade_date)::int as pnl_year,
  ticker,
  sum(realized_pnl) as realized_pnl,
  sum(case when trade_type = 'sell' then quantity else 0 end) as sold_qty,
  currency
from public.trades
where trade_type = 'sell' and realized_pnl is not null
group by 1, 2, currency;

grant select on public.v_realized_pnl to authenticated;

-- Unrealized PnL from current holdings
create or replace view public.v_unrealized_pnl as
select
  h.account_id,
  h.ticker,
  h.name,
  h.quantity,
  h.avg_price,
  mp.price as current_price,
  h.currency,
  (mp.price - h.avg_price) * h.quantity as unrealized_pnl,
  case when nullif(h.avg_price, 0) is null then null
       else (mp.price - h.avg_price) / h.avg_price * 100 end as return_rate
from public.holdings h
left join public.market_prices mp on mp.ticker = h.ticker;

grant select on public.v_unrealized_pnl to authenticated;

-- Keep OCR trade inserts from double-updating holdings (snapshot is authoritative)
create or replace function public.commit_ocr_staging()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_account_id uuid;
  v_trade jsonb;
  v_holding jsonb;
  v_created_by uuid;
begin
  if tg_op <> 'UPDATE' then
    return new;
  end if;

  if new.status is distinct from 'approved' then
    return new;
  end if;

  if old.status is not distinct from 'approved' then
    return new;
  end if;

  v_account_id := nullif(new.parsed_json->>'account_id', '')::uuid;
  if v_account_id is null then
    raise exception 'ocr_staging.parsed_json.account_id is required';
  end if;

  if not exists (select 1 from public.accounts a where a.id = v_account_id) then
    raise exception 'account_id % not found', v_account_id;
  end if;

  v_created_by := coalesce(new.reviewed_by, new.uploaded_by);

  if jsonb_typeof(coalesce(new.parsed_json->'trades', '[]'::jsonb)) = 'array' then
    for v_trade in
      select value from jsonb_array_elements(coalesce(new.parsed_json->'trades', '[]'::jsonb))
    loop
      insert into public.trades (
        account_id, trade_date, ticker, trade_type, price, quantity, reason, created_by, adjust_holdings
      ) values (
        v_account_id,
        coalesce((v_trade->>'trade_date')::date, current_date),
        v_trade->>'ticker',
        v_trade->>'trade_type',
        coalesce((v_trade->>'price')::numeric, 0),
        coalesce((v_trade->>'quantity')::numeric, 0),
        v_trade->>'reason',
        v_created_by,
        false
      );
    end loop;
  end if;

  if jsonb_typeof(coalesce(new.parsed_json->'holdings_snapshot', '[]'::jsonb)) = 'array' then
    for v_holding in
      select value from jsonb_array_elements(coalesce(new.parsed_json->'holdings_snapshot', '[]'::jsonb))
    loop
      insert into public.holdings (
        account_id, ticker, name, quantity, avg_price, currency, updated_at
      ) values (
        v_account_id,
        v_holding->>'ticker',
        v_holding->>'name',
        coalesce((v_holding->>'quantity')::numeric, 0),
        coalesce((v_holding->>'avg_price')::numeric, 0),
        coalesce(v_holding->>'currency', 'KRW'),
        now()
      )
      on conflict (account_id, ticker) do update
      set
        name = excluded.name,
        quantity = excluded.quantity,
        avg_price = excluded.avg_price,
        currency = excluded.currency,
        updated_at = now();
    end loop;
  end if;

  new.reviewed_at := coalesce(new.reviewed_at, now());
  return new;
end;
$$;
