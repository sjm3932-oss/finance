-- Toss 체결을 trades.external_id 로 중복 없이 저장한다.

alter table public.trades
  add column if not exists external_id text;

create unique index if not exists idx_trades_account_external
  on public.trades (account_id, external_id)
  where external_id is not null;

comment on column public.trades.external_id is
  'Broker order id (Toss orderId). Used to skip already-synced fills.';
