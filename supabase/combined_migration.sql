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

grant usage on schema public to authenticated;
grant select, insert, update, delete on all tables in schema public to authenticated;
grant usage, select on all sequences in schema public to authenticated;
alter default privileges in schema public
  grant select, insert, update, delete on tables to authenticated;


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


-- >>> 0006_daily_snapshot_and_cron.sql
-- 0006_daily_snapshot_and_cron.sql
-- Nightly net-worth snapshot + schedule hooks for Edge Functions.

create or replace function public.compute_daily_snapshot(p_date date default (timezone('Asia/Seoul', now()))::date)
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

  -- Investment market value in KRW (USD holdings converted)
  select coalesce(sum(
    case
      when coalesce(h.currency, 'KRW') = 'USD' then h.quantity * coalesce(mp.price, h.avg_price, 0) * v_usdkrw
      else h.quantity * coalesce(mp.price, h.avg_price, 0)
    end
  ), 0)
  into v_invest
  from public.holdings h
  left join public.market_prices mp on mp.ticker = h.ticker;

  select coalesce(sum(principal), 0) into v_debt from public.debts;

  -- Approximate cash as bank-type account holdings with ticker CASH if present; else 0
  select coalesce(sum(
    case
      when coalesce(h.currency, 'KRW') = 'USD' then h.quantity * coalesce(mp.price, 1) * v_usdkrw
      else h.quantity * coalesce(mp.price, 1)
    end
  ), 0)
  into v_cash
  from public.holdings h
  join public.accounts a on a.id = h.account_id
  left join public.market_prices mp on mp.ticker = h.ticker
  where a.account_type = 'bank';

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

-- Helper: invoke Edge Function via pg_net (URL/secret from vault or settings table)
create table if not exists public.app_settings (
  key text primary key,
  value text not null,
  updated_at timestamptz not null default now()
);

alter table public.app_settings enable row level security;

-- No authenticated policies: only service_role / security definer may read secrets.
drop policy if exists couple_select_app_settings on public.app_settings;
create or replace function public.invoke_edge_function(p_function_name text, p_body jsonb default '{}'::jsonb)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
  v_base text;
  v_key text;
  v_url text;
  v_request_id bigint;
begin
  select value into v_base from public.app_settings where key = 'supabase_url';
  select value into v_key from public.app_settings where key = 'service_role_key';

  if v_base is null or v_key is null then
    raise notice 'app_settings missing supabase_url/service_role_key — skip invoke %', p_function_name;
    return null;
  end if;

  v_url := rtrim(v_base, '/') || '/functions/v1/' || p_function_name;

  select net.http_post(
    url := v_url,
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || v_key
    ),
    body := p_body
  ) into v_request_id;

  return v_request_id;
end;
$$;

revoke all on function public.invoke_edge_function(text, jsonb) from public;

-- Backups bucket (private)
insert into storage.buckets (id, name, public, file_size_limit)
values ('backups', 'backups', false, 104857600)
on conflict (id) do update
set public = excluded.public,
    file_size_limit = excluded.file_size_limit;

drop policy if exists service_backups_all on storage.objects;
-- Storage policies for couple read of backups (optional)
drop policy if exists couple_select_backups on storage.objects;
create policy couple_select_backups on storage.objects
  for select to authenticated
  using (bucket_id = 'backups' and public.is_couple_member());


-- >>> 0007_schedule_cron_jobs.sql
-- 0007_schedule_cron_jobs.sql
-- Requires extensions pg_cron + pg_net (enabled on project).
-- Times are UTC: 00:00 KST=15:00 UTC, 08:00 KST=23:00 UTC, 01:00 KST=16:00 UTC.

create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;

-- Unschedule if re-applied
do $$
begin
  perform cron.unschedule(jobid)
  from cron.job
  where jobname in (
    'cwm_daily_snapshot',
    'cwm_morning_briefing',
    'cwm_refresh_prices',
    'cwm_nightly_backup'
  );
exception when undefined_table then
  null;
end $$;

-- 15:00 UTC = 00:00 KST — compute snapshot
select cron.schedule(
  'cwm_daily_snapshot',
  '0 15 * * *',
  $$select public.compute_daily_snapshot((timezone('Asia/Seoul', now()))::date);$$
);

-- Hourly price refresh via Edge Function (best-effort)
select cron.schedule(
  'cwm_refresh_prices',
  '15 * * * *',
  $$select public.invoke_edge_function('refresh-prices', '{}'::jsonb);$$
);

-- 23:00 UTC = 08:00 KST — morning briefing + push
select cron.schedule(
  'cwm_morning_briefing',
  '0 23 * * *',
  $$select public.invoke_edge_function('morning-briefing', '{}'::jsonb);$$
);

-- 16:00 UTC = 01:00 KST — nightly backup
select cron.schedule(
  'cwm_nightly_backup',
  '0 16 * * *',
  $$select public.invoke_edge_function('nightly-backup', '{}'::jsonb);$$
);


-- >>> 0008_holding_daily_snapshots.sql
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


-- >>> 0009_asset_flows.sql
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


