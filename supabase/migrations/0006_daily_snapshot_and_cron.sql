-- 0006_daily_snapshot_and_cron.sql
-- Nightly net-worth snapshot + schedule hooks for Edge Functions.

create or replace function public.compute_daily_snapshot(p_date date default (timezone('Asia/Seoul', now()))::date)
returns public.daily_snapshots
language plpgsql
security definer
set search_path = public
as $$
declare
  v_invest numeric := 0;
  v_debt numeric := 0;
  v_cash numeric := 0;
  v_net numeric := 0;
  v_cash_ratio numeric := 0;
  v_usdkrw numeric := 1;
  v_row public.daily_snapshots;
  v_date date := coalesce(p_date, (timezone('Asia/Seoul', now()))::date);
begin
  select coalesce(
    (select price from public.market_prices where ticker = 'USDKRW' limit 1),
    1
  ) into v_usdkrw;

  -- Investment market value in KRW (USD holdings converted)
  select coalesce(sum(
    case
      when coalesce(h.currency, 'KRW') = 'USD' then h.quantity * coalesce(mp.price, h.avg_price, 0) * v_usdkrw
      else h.quantity * coalesce(mp.price, h.avg_price, 0)
    end
  ), 0)
  into v_invest
  from public.holdings h
  left join public.market_prices mp on mp.ticker = h.ticker;

  select coalesce(sum(principal), 0) into v_debt from public.debts;

  -- Approximate cash as bank-type account holdings with ticker CASH if present; else 0
  select coalesce(sum(
    case
      when coalesce(h.currency, 'KRW') = 'USD' then h.quantity * coalesce(mp.price, 1) * v_usdkrw
      else h.quantity * coalesce(mp.price, 1)
    end
  ), 0)
  into v_cash
  from public.holdings h
  join public.accounts a on a.id = h.account_id
  left join public.market_prices mp on mp.ticker = h.ticker
  where a.account_type = 'bank';

  v_net := v_invest - v_debt;
  if v_invest > 0 then
    v_cash_ratio := v_cash / v_invest;
  else
    v_cash_ratio := 0;
  end if;

  insert into public.daily_snapshots as ds (
    snapshot_date, net_assets, total_investment, total_debt, cash_ratio
  ) values (
    v_date, v_net, v_invest, v_debt, v_cash_ratio
  )
  on conflict (snapshot_date) do update
  set
    net_assets = excluded.net_assets,
    total_investment = excluded.total_investment,
    total_debt = excluded.total_debt,
    cash_ratio = excluded.cash_ratio
  returning * into v_row;

  return v_row;
end;
$$;

revoke all on function public.compute_daily_snapshot(date) from public;
grant execute on function public.compute_daily_snapshot(date) to authenticated;
grant execute on function public.compute_daily_snapshot(date) to service_role;

-- Helper: invoke Edge Function via pg_net (URL/secret from vault or settings table)
create table if not exists public.app_settings (
  key text primary key,
  value text not null,
  updated_at timestamptz not null default now()
);

alter table public.app_settings enable row level security;

-- No authenticated policies: only service_role / security definer may read secrets.
drop policy if exists couple_select_app_settings on public.app_settings;
create or replace function public.invoke_edge_function(p_function_name text, p_body jsonb default '{}'::jsonb)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
  v_base text;
  v_key text;
  v_url text;
  v_request_id bigint;
begin
  select value into v_base from public.app_settings where key = 'supabase_url';
  select value into v_key from public.app_settings where key = 'service_role_key';

  if v_base is null or v_key is null then
    raise notice 'app_settings missing supabase_url/service_role_key — skip invoke %', p_function_name;
    return null;
  end if;

  v_url := rtrim(v_base, '/') || '/functions/v1/' || p_function_name;

  select net.http_post(
    url := v_url,
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || v_key
    ),
    body := p_body
  ) into v_request_id;

  return v_request_id;
end;
$$;

revoke all on function public.invoke_edge_function(text, jsonb) from public;

-- Backups bucket (private)
insert into storage.buckets (id, name, public, file_size_limit)
values ('backups', 'backups', false, 104857600)
on conflict (id) do update
set public = excluded.public,
    file_size_limit = excluded.file_size_limit;

drop policy if exists service_backups_all on storage.objects;
-- Storage policies for couple read of backups (optional)
drop policy if exists couple_select_backups on storage.objects;
create policy couple_select_backups on storage.objects
  for select to authenticated
  using (bucket_id = 'backups' and public.is_couple_member());
