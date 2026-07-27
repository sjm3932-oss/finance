-- 0016_watchlist_kospi.sql
-- Watchlist + price alerts; KOSPI on market_index_snapshots

-- ---- KOSPI on index snapshots ----
alter table public.market_index_snapshots
  add column if not exists kospi numeric;

-- ---- Watchlist (관심종목 + 목표가/손절가) ----
create table if not exists public.watchlist (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  ticker text not null,
  name text,
  target_price numeric,
  stop_price numeric,
  note text,
  created_at timestamptz not null default now(),
  unique (user_id, ticker)
);

create index if not exists idx_watchlist_user on public.watchlist(user_id);
create index if not exists idx_watchlist_ticker on public.watchlist(ticker);

alter table public.watchlist enable row level security;
drop policy if exists couple_all_watchlist on public.watchlist;
create policy couple_all_watchlist on public.watchlist
  for all to authenticated
  using (public.is_couple_member())
  with check (
    public.is_couple_member()
    and user_id in (select id from public.users)
  );

grant select, insert, update, delete on public.watchlist to authenticated;

-- ---- Price alert events (in-app log; triggered when prices refresh) ----
create table if not exists public.price_alert_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  watchlist_id uuid references public.watchlist(id) on delete set null,
  ticker text not null,
  alert_kind text not null check (alert_kind in ('target', 'stop')),
  trigger_price numeric not null,
  market_price numeric not null,
  acknowledged boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists idx_price_alert_user_ack
  on public.price_alert_events(user_id, acknowledged, created_at desc);

alter table public.price_alert_events enable row level security;
drop policy if exists couple_all_price_alert_events on public.price_alert_events;
create policy couple_all_price_alert_events on public.price_alert_events
  for all to authenticated
  using (public.is_couple_member())
  with check (
    public.is_couple_member()
    and user_id in (select id from public.users)
  );

grant select, insert, update, delete on public.price_alert_events to authenticated;
