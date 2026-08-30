-- Queue for Toss holdings sync. Edge Functions only enqueue; a cloud VM
-- with a static IP performs the Open API calls.

create table if not exists public.toss_sync_jobs (
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

create index if not exists toss_sync_jobs_queued_idx
  on public.toss_sync_jobs (created_at)
  where status = 'queued';

create table if not exists public.toss_sync_worker (
  id int primary key default 1 check (id = 1),
  public_ip text,
  seen_at timestamptz not null default now()
);

insert into public.toss_sync_worker (id)
values (1)
on conflict (id) do nothing;

alter table public.toss_sync_jobs enable row level security;
alter table public.toss_sync_worker enable row level security;

drop policy if exists couple_select_toss_sync_jobs on public.toss_sync_jobs;
create policy couple_select_toss_sync_jobs on public.toss_sync_jobs
  for select to authenticated
  using (public.is_couple_member());

drop policy if exists couple_insert_toss_sync_jobs on public.toss_sync_jobs;
create policy couple_insert_toss_sync_jobs on public.toss_sync_jobs
  for insert to authenticated
  with check (user_id = auth.uid() and public.is_couple_member());

drop policy if exists couple_select_toss_sync_worker on public.toss_sync_worker;
create policy couple_select_toss_sync_worker on public.toss_sync_worker
  for select to authenticated
  using (public.is_couple_member());

create or replace function public.claim_toss_sync_job()
returns public.toss_sync_jobs
language plpgsql
security definer
set search_path = public
as $$
declare
  job public.toss_sync_jobs;
begin
  select * into job
  from public.toss_sync_jobs
  where status = 'queued'
  order by created_at
  for update skip locked
  limit 1;

  if not found then
    return null;
  end if;

  update public.toss_sync_jobs
  set status = 'running', started_at = now()
  where id = job.id
  returning * into job;

  return job;
end;
$$;

revoke all on function public.claim_toss_sync_job() from public;
grant execute on function public.claim_toss_sync_job() to service_role;

create or replace function public.touch_toss_sync_worker(p_ip text)
returns void
language sql
security definer
set search_path = public
as $$
  insert into public.toss_sync_worker (id, public_ip, seen_at)
  values (1, p_ip, now())
  on conflict (id) do update
    set public_ip = excluded.public_ip,
        seen_at = excluded.seen_at;
$$;

revoke all on function public.touch_toss_sync_worker(text) from public;
grant execute on function public.touch_toss_sync_worker(text) to service_role;
