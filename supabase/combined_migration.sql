-- Auto-generated combined migration for Couples Wealth Master
-- Project: https://lsqkixysysfhywipmrky.supabase.co
-- Apply in Supabase Dashboard → SQL → New query

-- >>> 0001_schema.sql
-- 0001_schema.sql — Couples Wealth Master core tables

create extension if not exists "pgcrypto";

-- 3.1 users (id mirrors auth.users)
create table if not exists public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  email text unique not null,
  display_name text not null,
  created_at timestamptz not null default now()
);

-- 3.2 accounts
create table if not exists public.accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  institution text not null,
  account_type text not null check (account_type in ('brokerage', 'bank', 'loan')),
  currency text not null default 'KRW',
  created_at timestamptz not null default now()
);

-- 3.3 holdings
create table if not exists public.holdings (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.accounts(id) on delete cascade,
  ticker text not null,
  name text,
  quantity numeric not null default 0,
  avg_price numeric not null default 0,
  currency text not null default 'KRW',
  updated_at timestamptz not null default now(),
  unique (account_id, ticker)
);

-- 3.4 market_prices
create table if not exists public.market_prices (
  ticker text primary key,
  price numeric not null,
  currency text not null,
  updated_at timestamptz not null default now()
);

-- 3.5 trades
create table if not exists public.trades (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.accounts(id) on delete cascade,
  trade_date date not null,
  ticker text not null,
  trade_type text not null check (trade_type in ('buy', 'sell')),
  price numeric not null,
  quantity numeric not null,
  reason text,
  created_by uuid not null references public.users(id),
  created_at timestamptz not null default now()
);

-- 3.6 cash_flows
create table if not exists public.cash_flows (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  flow_date date not null,
  category text not null,
  amount numeric not null,
  flow_type text not null check (flow_type in ('income', 'expense')),
  memo text,
  created_at timestamptz not null default now()
);

-- 3.7 debts
create table if not exists public.debts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  lender text not null,
  principal numeric not null,
  interest_rate numeric not null,
  due_date date,
  memo text,
  created_at timestamptz not null default now()
);

-- 3.8 daily_snapshots
create table if not exists public.daily_snapshots (
  snapshot_date date primary key,
  net_assets numeric not null,
  total_investment numeric not null,
  total_debt numeric not null,
  cash_ratio numeric not null
);

-- 3.9 market_index_snapshots
create table if not exists public.market_index_snapshots (
  snapshot_date date primary key,
  nasdaq numeric,
  sp500 numeric,
  usdkrw numeric
);

-- 3.10 tax_records
create table if not exists public.tax_records (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  tax_year int not null,
  cum_capital_gain numeric not null default 0,
  tax_threshold numeric not null default 2500000,
  dividend_tax numeric not null default 0,
  updated_at timestamptz not null default now(),
  unique (user_id, tax_year)
);

-- 3.11 ai_chat_logs
create table if not exists public.ai_chat_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.users(id) on delete set null,
  user_query text not null,
  ai_response text not null,
  context_summary text,
  created_at timestamptz not null default now()
);

-- 3.12 ocr_staging (includes failed status)
create table if not exists public.ocr_staging (
  id uuid primary key default gen_random_uuid(),
  uploaded_by uuid not null references public.users(id),
  image_url text not null,
  parsed_json jsonb not null default '{}'::jsonb,
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected', 'failed')),
  reviewed_by uuid references public.users(id),
  reviewed_at timestamptz,
  created_at timestamptz not null default now()
);

-- 3.13 push_subscriptions
create table if not exists public.push_subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  endpoint text not null,
  p256dh_key text not null,
  auth_key text not null,
  created_at timestamptz not null default now(),
  unique (user_id, endpoint)
);

create index if not exists idx_accounts_user_id on public.accounts(user_id);
create index if not exists idx_holdings_account_id on public.holdings(account_id);
create index if not exists idx_trades_account_id on public.trades(account_id);
create index if not exists idx_ocr_staging_status on public.ocr_staging(status);
create index if not exists idx_ocr_staging_uploaded_by on public.ocr_staging(uploaded_by);

-- Private storage bucket for OCR screenshots
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'ocr-screenshots',
  'ocr-screenshots',
  false,
  52428800,
  array['image/png', 'image/jpeg', 'image/webp', 'image/gif']
)
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;


-- >>> 0002_rls.sql
-- 0002_rls.sql — Couple-wide Row Level Security
-- Any authenticated user present in public.users may access couple data.

create or replace function public.is_couple_member()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.users u where u.id = auth.uid()
  );
$$;

revoke all on function public.is_couple_member() from public;
grant execute on function public.is_couple_member() to authenticated;

alter table public.users enable row level security;
alter table public.accounts enable row level security;
alter table public.holdings enable row level security;
alter table public.market_prices enable row level security;
alter table public.trades enable row level security;
alter table public.cash_flows enable row level security;
alter table public.debts enable row level security;
alter table public.daily_snapshots enable row level security;
alter table public.market_index_snapshots enable row level security;
alter table public.tax_records enable row level security;
alter table public.ai_chat_logs enable row level security;
alter table public.ocr_staging enable row level security;
alter table public.push_subscriptions enable row level security;

-- users
drop policy if exists couple_select_users on public.users;
create policy couple_select_users on public.users
  for select to authenticated
  using (public.is_couple_member());

drop policy if exists couple_insert_self_user on public.users;
create policy couple_insert_self_user on public.users
  for insert to authenticated
  with check (id = auth.uid());

drop policy if exists couple_update_self_user on public.users;
create policy couple_update_self_user on public.users
  for update to authenticated
  using (id = auth.uid())
  with check (id = auth.uid());

-- accounts
drop policy if exists couple_all_accounts on public.accounts;
create policy couple_all_accounts on public.accounts
  for all to authenticated
  using (public.is_couple_member())
  with check (
    public.is_couple_member()
    and user_id in (select id from public.users)
  );

-- holdings (via couple membership; account must exist in couple)
drop policy if exists couple_all_holdings on public.holdings;
create policy couple_all_holdings on public.holdings
  for all to authenticated
  using (public.is_couple_member())
  with check (
    public.is_couple_member()
    and exists (select 1 from public.accounts a where a.id = account_id)
  );

-- market_prices: shared cache readable/writable by couple
drop policy if exists couple_all_market_prices on public.market_prices;
create policy couple_all_market_prices on public.market_prices
  for all to authenticated
  using (public.is_couple_member())
  with check (public.is_couple_member());

-- trades
drop policy if exists couple_all_trades on public.trades;
create policy couple_all_trades on public.trades
  for all to authenticated
  using (public.is_couple_member())
  with check (
    public.is_couple_member()
    and created_by = auth.uid()
    and exists (select 1 from public.accounts a where a.id = account_id)
  );

-- cash_flows
drop policy if exists couple_all_cash_flows on public.cash_flows;
create policy couple_all_cash_flows on public.cash_flows
  for all to authenticated
  using (public.is_couple_member())
  with check (
    public.is_couple_member()
    and user_id in (select id from public.users)
  );

-- debts
drop policy if exists couple_all_debts on public.debts;
create policy couple_all_debts on public.debts
  for all to authenticated
  using (public.is_couple_member())
  with check (
    public.is_couple_member()
    and user_id in (select id from public.users)
  );

-- daily_snapshots / market_index_snapshots
drop policy if exists couple_all_daily_snapshots on public.daily_snapshots;
create policy couple_all_daily_snapshots on public.daily_snapshots
  for all to authenticated
  using (public.is_couple_member())
  with check (public.is_couple_member());

drop policy if exists couple_all_market_index_snapshots on public.market_index_snapshots;
create policy couple_all_market_index_snapshots on public.market_index_snapshots
  for all to authenticated
  using (public.is_couple_member())
  with check (public.is_couple_member());

-- tax_records
drop policy if exists couple_all_tax_records on public.tax_records;
create policy couple_all_tax_records on public.tax_records
  for all to authenticated
  using (public.is_couple_member())
  with check (
    public.is_couple_member()
    and user_id in (select id from public.users)
  );

-- ai_chat_logs
drop policy if exists couple_all_ai_chat_logs on public.ai_chat_logs;
create policy couple_all_ai_chat_logs on public.ai_chat_logs
  for all to authenticated
  using (public.is_couple_member())
  with check (public.is_couple_member());

-- ocr_staging: any couple member can read/update; only uploader inserts
drop policy if exists couple_select_ocr_staging on public.ocr_staging;
create policy couple_select_ocr_staging on public.ocr_staging
  for select to authenticated
  using (public.is_couple_member());

drop policy if exists couple_insert_ocr_staging on public.ocr_staging;
create policy couple_insert_ocr_staging on public.ocr_staging
  for insert to authenticated
  with check (
    public.is_couple_member()
    and uploaded_by = auth.uid()
  );

drop policy if exists couple_update_ocr_staging on public.ocr_staging;
create policy couple_update_ocr_staging on public.ocr_staging
  for update to authenticated
  using (public.is_couple_member())
  with check (public.is_couple_member());

drop policy if exists couple_delete_ocr_staging on public.ocr_staging;
create policy couple_delete_ocr_staging on public.ocr_staging
  for delete to authenticated
  using (public.is_couple_member());

-- push_subscriptions
drop policy if exists couple_all_push_subscriptions on public.push_subscriptions;
create policy couple_all_push_subscriptions on public.push_subscriptions
  for all to authenticated
  using (public.is_couple_member())
  with check (
    public.is_couple_member()
    and user_id = auth.uid()
  );

-- Storage: OCR screenshots — couple members only
drop policy if exists couple_select_ocr_screenshots on storage.objects;
create policy couple_select_ocr_screenshots on storage.objects
  for select to authenticated
  using (
    bucket_id = 'ocr-screenshots'
    and public.is_couple_member()
  );

drop policy if exists couple_insert_ocr_screenshots on storage.objects;
create policy couple_insert_ocr_screenshots on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'ocr-screenshots'
    and public.is_couple_member()
  );

drop policy if exists couple_update_ocr_screenshots on storage.objects;
create policy couple_update_ocr_screenshots on storage.objects
  for update to authenticated
  using (
    bucket_id = 'ocr-screenshots'
    and public.is_couple_member()
  )
  with check (
    bucket_id = 'ocr-screenshots'
    and public.is_couple_member()
  );

drop policy if exists couple_delete_ocr_screenshots on storage.objects;
create policy couple_delete_ocr_screenshots on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'ocr-screenshots'
    and public.is_couple_member()
  );


-- >>> 0003_views.sql
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


-- >>> 0004_ocr_commit_trigger.sql
-- 0004_ocr_commit_trigger.sql
-- When ocr_staging.status becomes 'approved', commit trades + holdings.

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

  -- Only run on transition into approved
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

  -- Insert trades
  if jsonb_typeof(coalesce(new.parsed_json->'trades', '[]'::jsonb)) = 'array' then
    for v_trade in
      select value from jsonb_array_elements(coalesce(new.parsed_json->'trades', '[]'::jsonb))
    loop
      insert into public.trades (
        account_id,
        trade_date,
        ticker,
        trade_type,
        price,
        quantity,
        reason,
        created_by
      ) values (
        v_account_id,
        coalesce((v_trade->>'trade_date')::date, current_date),
        v_trade->>'ticker',
        v_trade->>'trade_type',
        coalesce((v_trade->>'price')::numeric, 0),
        coalesce((v_trade->>'quantity')::numeric, 0),
        v_trade->>'reason',
        v_created_by
      );
    end loop;
  end if;

  -- Upsert holdings snapshot (optional)
  if jsonb_typeof(coalesce(new.parsed_json->'holdings_snapshot', '[]'::jsonb)) = 'array' then
    for v_holding in
      select value from jsonb_array_elements(coalesce(new.parsed_json->'holdings_snapshot', '[]'::jsonb))
    loop
      insert into public.holdings (
        account_id,
        ticker,
        name,
        quantity,
        avg_price,
        currency,
        updated_at
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

drop trigger if exists trg_commit_ocr_staging on public.ocr_staging;
create trigger trg_commit_ocr_staging
  before update on public.ocr_staging
  for each row
  execute function public.commit_ocr_staging();


-- >>> 0005_allowed_emails.sql
-- 0005_allowed_emails.sql — DB-level email allow-list for couple membership

create table if not exists public.allowed_emails (
  email text primary key,
  created_at timestamptz not null default now()
);

alter table public.allowed_emails enable row level security;

-- Only existing couple members can read; bootstrap inserts use service role
drop policy if exists couple_select_allowed_emails on public.allowed_emails;
create policy couple_select_allowed_emails on public.allowed_emails
  for select to authenticated
  using (public.is_couple_member());

create or replace function public.email_is_allowed(p_email text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.allowed_emails ae
    where lower(ae.email) = lower(p_email)
  )
  -- If allow-list is empty, fall back to app-layer ALLOWED_EMAILS only
  or not exists (select 1 from public.allowed_emails);
$$;

revoke all on function public.email_is_allowed(text) from public;
grant execute on function public.email_is_allowed(text) to authenticated;

create or replace function public.register_couple_user(
  p_display_name text default null
)
returns public.users
language plpgsql
security definer
set search_path = public
as $$
declare
  v_email text;
  v_row public.users;
begin
  if auth.uid() is null then
    raise exception 'Not authenticated';
  end if;

  select u.email into v_email from auth.users u where u.id = auth.uid();
  if v_email is null then
    raise exception 'Auth user email not found';
  end if;

  if not public.email_is_allowed(v_email) then
    raise exception 'Email % is not in allowed_emails', v_email;
  end if;

  insert into public.users (id, email, display_name)
  values (
    auth.uid(),
    lower(v_email),
    coalesce(nullif(trim(p_display_name), ''), split_part(v_email, '@', 1))
  )
  on conflict (id) do update
    set email = excluded.email,
        display_name = coalesce(nullif(trim(p_display_name), ''), public.users.display_name)
  returning * into v_row;

  return v_row;
end;
$$;

revoke all on function public.register_couple_user(text) from public;
grant execute on function public.register_couple_user(text) to authenticated;

-- Tighten self-insert: must be allow-listed
drop policy if exists couple_insert_self_user on public.users;
create policy couple_insert_self_user on public.users
  for insert to authenticated
  with check (
    id = auth.uid()
    and public.email_is_allowed(email)
  );


