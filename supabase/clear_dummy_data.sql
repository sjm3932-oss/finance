-- Wipe demo/dummy transactional data for the couple DB.
-- Keeps Auth users + public.users + allowed_emails + market_prices
-- + ai_chat_logs + market_index_snapshots
-- + real accounts whose institution is 한국투자증권.
-- Seed dummy institutions: 토스증권, 키움증권, 카카오뱅크.
--
-- Run in Supabase Dashboard → SQL Editor → New query → Run.
-- Optional tables (other_assets, watchlist, …) are skipped if missing.

begin;

-- OCR staging
delete from public.ocr_staging;

-- Dummy debts only (seed memo: 더미 주담대)
delete from public.debt_transactions
where debt_id in (select id from public.debts where coalesce(memo, '') like '%더미%');
delete from public.debt_rate_history
where debt_id in (select id from public.debts where coalesce(memo, '') like '%더미%');
delete from public.debts
where coalesce(memo, '') like '%더미%';

-- Dummy-account ledger (keep 한국투자증권)
delete from public.dividends
where account_id in (
  select id from public.accounts
  where institution in ('토스증권', '키움증권', '카카오뱅크')
);
delete from public.cash_flows
where account_id in (
  select id from public.accounts
  where institution in ('토스증권', '키움증권', '카카오뱅크')
);
delete from public.trades
where account_id in (
  select id from public.accounts
  where institution in ('토스증권', '키움증권', '카카오뱅크')
);
delete from public.holding_daily_snapshots
where account_id in (
  select id from public.accounts
  where institution in ('토스증권', '키움증권', '카카오뱅크')
);
delete from public.holdings
where account_id in (
  select id from public.accounts
  where institution in ('토스증권', '키움증권', '카카오뱅크')
);

-- Seed tax row (dummy portfolio). Real tax can be re-entered after live trades.
delete from public.tax_records;

-- Optional wealth extras if 0017 has been applied
do $$
begin
  if to_regclass('public.other_assets') is not null then
    delete from public.other_assets;
  end if;
  if to_regclass('public.wealth_alert_events') is not null then
    delete from public.wealth_alert_events;
  end if;
  if to_regclass('public.price_alert_events') is not null then
    delete from public.price_alert_events;
  end if;
  if to_regclass('public.watchlist') is not null then
    delete from public.watchlist;
  end if;
end $$;

-- Dummy net-worth history (includes seed holdings). Keep market_index_snapshots.
delete from public.daily_snapshots;

-- Dummy seed accounts only
delete from public.accounts
where institution in ('토스증권', '키움증권', '카카오뱅크');

-- Keep market_prices (USDKRW etc.) for FX/display.
-- Keep ai_chat_logs (real conversations).
-- Keep 한국투자증권.

-- Reset allocation targets to defaults
insert into public.allocation_targets (category, target_pct, updated_at)
values
  ('domestic', 40, now()),
  ('overseas', 40, now()),
  ('cash', 15, now()),
  ('other', 5, now())
on conflict (category) do update
set target_pct = excluded.target_pct,
    updated_at = excluded.updated_at;

commit;
