-- Parent/child home filters: 소유 > 금융기관.
-- Existing accounts belong to 정명 (mine). New accounts default to 정명.
-- Safe if 0017 already added ownership (default joint): we re-tag and change default.

alter table public.accounts
  add column if not exists ownership text not null default 'mine';

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'accounts_ownership_check'
  ) then
    alter table public.accounts
      add constraint accounts_ownership_check
      check (ownership in ('joint', 'mine', 'spouse'));
  end if;
end $$;

update public.accounts
set ownership = 'mine'
where ownership is distinct from 'mine';

alter table public.accounts
  alter column ownership set default 'mine';

comment on column public.accounts.ownership is 'joint | mine | spouse';
