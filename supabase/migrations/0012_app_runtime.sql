-- Live Streamlit origins published by tunnel keepers.
create table if not exists public.app_runtime (
  id int primary key default 1 check (id = 1),
  public_url text not null,
  fallback_url text,
  updated_at timestamptz not null default now()
);

alter table public.app_runtime enable row level security;

drop policy if exists "app_runtime_select_all" on public.app_runtime;
create policy "app_runtime_select_all"
  on public.app_runtime
  for select
  to anon, authenticated
  using (true);

insert into public.app_runtime (id, public_url)
values (1, 'http://localhost:8501')
on conflict (id) do nothing;

alter table public.app_runtime
  add column if not exists fallback_url text;

create or replace function public.touch_app_runtime_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_app_runtime_updated_at on public.app_runtime;
create trigger trg_app_runtime_updated_at
  before update on public.app_runtime
  for each row execute function public.touch_app_runtime_updated_at();
