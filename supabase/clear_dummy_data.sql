-- Wipe demo/dummy transactional data for the couple DB.
-- Run in Supabase Dashboard → SQL Editor → New query → Run.
-- Keeps Auth users + public.users profile rows.
-- After this, add real accounts in Next 「기록 → 계좌」.

begin;

-- OCR staging + related
delete from ocr_staging;

-- Debt children then debts
delete from debt_transactions;
delete from debt_rate_history;
delete from debts;

-- Ledger
delete from dividends;
delete from cash_flows;
delete from tax_records;
delete from trades;

-- Holdings + history
delete from holding_daily_snapshots;
delete from holdings;

-- Wealth extras (may not exist on older DBs — ignore errors by running separately if needed)
delete from other_assets;
delete from wealth_alert_events;

-- Snapshots / indexes
delete from daily_snapshots;
delete from market_index_snapshots;

-- Accounts last (dummy 토스/키움/카카오 등)
delete from accounts;

-- Optional: clear demo market prices (USDKRW 등). Keep if you still want FX/prices.
-- delete from market_prices;

-- Reset allocation targets to defaults (optional)
insert into allocation_targets (category, target_pct, updated_at)
values
  ('domestic', 40, now()),
  ('overseas', 40, now()),
  ('cash', 15, now()),
  ('other', 5, now())
on conflict (category) do update
set target_pct = excluded.target_pct,
    updated_at = excluded.updated_at;

commit;
