-- Wipe demo/dummy transactional data for the couple DB.
-- Run in Supabase Dashboard → SQL Editor → New query → Run.
-- Keeps Auth users + public.users + allowed_emails.
-- After this, add real accounts in Next 「더보기 → 기록하기 → 계좌」.

begin;

-- OCR staging
delete from public.ocr_staging;

-- Debt children then debts
delete from public.debt_transactions;
delete from public.debt_rate_history;
delete from public.debts;

-- Ledger
delete from public.dividends;
delete from public.cash_flows;
delete from public.tax_records;
delete from public.trades;

-- Holdings + history
delete from public.holding_daily_snapshots;
delete from public.holdings;

-- Wealth extras
delete from public.other_assets;
delete from public.wealth_alert_events;

-- Optional watchlist / price alerts (if present)
delete from public.price_alert_events;
delete from public.watchlist;

-- Chat demo history (optional clean slate for real use)
delete from public.ai_chat_logs;

-- Snapshots / indexes
delete from public.daily_snapshots;
delete from public.market_index_snapshots;

-- Accounts last (dummy 토스/키움/카카오 등)
delete from public.accounts;

-- Keep market_prices (USDKRW etc.) for FX/display.
-- Uncomment to wipe prices too:
-- delete from public.market_prices;

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
