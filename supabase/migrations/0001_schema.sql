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
