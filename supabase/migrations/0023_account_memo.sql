-- Optional memo on brokerage/bank/loan accounts (same idea as other_assets.memo).

alter table public.accounts
  add column if not exists memo text;

comment on column public.accounts.memo is 'Optional free-text note (account number last digits, ISA, etc.)';
