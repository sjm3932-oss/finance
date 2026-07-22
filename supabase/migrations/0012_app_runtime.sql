-- Stable public pointer to the live Streamlit URL (updated by tunnel keeper).
create table if not exists public.app_runtime (
  id int primary key default 1 check (id = 1),
  public_url text not null,
  updated_at timestamptz not null default now()
);

alter table public.app_runtime enable row level security;

drop policy if exists "app_runtime_select_all" on public.app_runtime;
create policy "app_runtime_select_all"
  on public.app_runtime
  for select
  to anon, authenticated
  using (true);

-- Writes only via service role (no insert/update policies for anon).

insert into public.app_runtime (id, public_url)
values (1, 'http://localhost:8501')
on conflict (id) do nothing;
