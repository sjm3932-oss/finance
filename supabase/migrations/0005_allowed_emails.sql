-- 0005_allowed_emails.sql — DB-level email allow-list for couple membership

create table if not exists public.allowed_emails (
  email text primary key,
  created_at timestamptz not null default now()
);

alter table public.allowed_emails enable row level security;

-- Only existing couple members can read; bootstrap inserts use service role
drop policy if exists couple_select_allowed_emails on public.allowed_emails;
create policy couple_select_allowed_emails on public.allowed_emails
  for select to authenticated
  using (public.is_couple_member());

create or replace function public.email_is_allowed(p_email text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.allowed_emails ae
    where lower(ae.email) = lower(p_email)
  )
  -- If allow-list is empty, fall back to app-layer ALLOWED_EMAILS only
  or not exists (select 1 from public.allowed_emails);
$$;

revoke all on function public.email_is_allowed(text) from public;
grant execute on function public.email_is_allowed(text) to authenticated;

create or replace function public.register_couple_user(
  p_display_name text default null
)
returns public.users
language plpgsql
security definer
set search_path = public
as $$
declare
  v_email text;
  v_row public.users;
begin
  if auth.uid() is null then
    raise exception 'Not authenticated';
  end if;

  select u.email into v_email from auth.users u where u.id = auth.uid();
  if v_email is null then
    raise exception 'Auth user email not found';
  end if;

  if not public.email_is_allowed(v_email) then
    raise exception 'Email % is not in allowed_emails', v_email;
  end if;

  insert into public.users (id, email, display_name)
  values (
    auth.uid(),
    lower(v_email),
    coalesce(nullif(trim(p_display_name), ''), split_part(v_email, '@', 1))
  )
  on conflict (id) do update
    set email = excluded.email,
        display_name = coalesce(nullif(trim(p_display_name), ''), public.users.display_name)
  returning * into v_row;

  return v_row;
end;
$$;

revoke all on function public.register_couple_user(text) from public;
grant execute on function public.register_couple_user(text) to authenticated;

-- Tighten self-insert: must be allow-listed
drop policy if exists couple_insert_self_user on public.users;
create policy couple_insert_self_user on public.users
  for insert to authenticated
  with check (
    id = auth.uid()
    and public.email_is_allowed(email)
  );
