-- Queue for Korea Investment (한투) holdings / trades / dividends sync.
-- Edge Functions only enqueue; the same static-IP cloud worker as Toss
-- (toss_sync_worker heartbeat) performs the Open API calls.

create table if not exists public.kis_sync_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  status text not null default 'queued'
    check (status in ('queued', 'running', 'ok', 'error')),
  error text,
  result jsonb,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz
);

create index if not exists kis_sync_jobs_queued_idx
  on public.kis_sync_jobs (created_at)
  where status = 'queued';

alter table public.kis_sync_jobs enable row level security;

drop policy if exists couple_select_kis_sync_jobs on public.kis_sync_jobs;
create policy couple_select_kis_sync_jobs on public.kis_sync_jobs
  for select to authenticated
  using (public.is_couple_member());

drop policy if exists couple_insert_kis_sync_jobs on public.kis_sync_jobs;
create policy couple_insert_kis_sync_jobs on public.kis_sync_jobs
  for insert to authenticated
  with check (user_id = auth.uid() and public.is_couple_member());

create or replace function public.claim_kis_sync_job()
returns public.kis_sync_jobs
language plpgsql
security definer
set search_path = public
as $$
declare
  job public.kis_sync_jobs;
begin
  select * into job
  from public.kis_sync_jobs
  where status = 'queued'
  order by created_at
  for update skip locked
  limit 1;

  if not found then
    return null;
  end if;

  update public.kis_sync_jobs
  set status = 'running', started_at = now()
  where id = job.id
  returning * into job;

  return job;
end;
$$;

revoke all on function public.claim_kis_sync_job() from public;
grant execute on function public.claim_kis_sync_job() to service_role;

-- Broker-sourced dividends: skip duplicates via external_id (한투 권리/거래 키).
alter table public.dividends
  add column if not exists external_id text;

create unique index if not exists idx_dividends_account_external
  on public.dividends (account_id, external_id)
  where external_id is not null;

comment on column public.dividends.external_id is
  'Broker event id (KIS right/trans). Used to skip already-synced dividends.';

comment on column public.trades.external_id is
  'Broker order id (Toss orderId or KIS odno). Used to skip already-synced fills.';
