-- 0018_tighten_email_allowlist.sql
-- Empty allowed_emails must NOT mean "allow everyone".

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
    where lower(ae.email) = lower(trim(p_email))
  );
$$;

revoke all on function public.email_is_allowed(text) from public;
grant execute on function public.email_is_allowed(text) to authenticated;
grant execute on function public.email_is_allowed(text) to service_role;

comment on function public.email_is_allowed(text) is
  'True only when email is present in public.allowed_emails. Empty table denies all.';
