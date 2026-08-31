-- Couple-wide KIS (한투) Open API credentials.
-- Saved from the in-app 한투 동기화 form so SSH / worker env is not required.
-- RLS on, no authenticated policies: PostgREST cannot read app_secret.
-- Edge Functions and the Python worker use the service role (bypasses RLS).

create table if not exists public.kis_api_settings (
  id int primary key default 1 check (id = 1),
  app_key text not null default '',
  app_secret text not null default '',
  accounts text not null default '',
  env text not null default 'real' check (env in ('real', 'demo')),
  access_token text,
  token_expires_at timestamptz,
  updated_at timestamptz not null default now(),
  updated_by uuid references public.users(id)
);

insert into public.kis_api_settings (id)
values (1)
on conflict (id) do nothing;

alter table public.kis_api_settings enable row level security;

revoke all on public.kis_api_settings from public, anon, authenticated;
grant select, insert, update on public.kis_api_settings to service_role;

comment on table public.kis_api_settings is
  'Singleton KIS app key/secret. Couple members save via kis-sync Edge Function; never expose app_secret over RLS.';
