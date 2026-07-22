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
