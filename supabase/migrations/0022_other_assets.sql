-- other_assets: 부동산·연금·보험 등 (계좌가 아님)
-- 0017 already defines this; create if missing so 기록하기 → 순자산 추가가 동작한다.

create table if not exists public.other_assets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  name text not null,
  asset_kind text not null
    check (asset_kind in (
      'real_estate', 'pension', 'insurance', 'deposit', 'crypto', 'other'
    )),
  value_krw numeric not null default 0,
  ownership text not null default 'joint'
    check (ownership in ('joint', 'mine', 'spouse')),
  memo text,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists idx_other_assets_user on public.other_assets(user_id);

alter table public.other_assets enable row level security;

drop policy if exists couple_all_other_assets on public.other_assets;
create policy couple_all_other_assets on public.other_assets
  for all to authenticated
  using (public.is_couple_member())
  with check (
    public.is_couple_member()
    and user_id in (select id from public.users)
  );

grant select, insert, update, delete on public.other_assets to authenticated;
grant select, insert, update, delete on public.other_assets to service_role;
