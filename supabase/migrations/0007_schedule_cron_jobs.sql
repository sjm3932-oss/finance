-- 0007_schedule_cron_jobs.sql
-- Requires extensions pg_cron + pg_net (enabled on project).
-- Times are UTC: 00:00 KST=15:00 UTC, 08:00 KST=23:00 UTC, 01:00 KST=16:00 UTC.

create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;

-- Unschedule if re-applied
do $$
begin
  perform cron.unschedule(jobid)
  from cron.job
  where jobname in (
    'cwm_daily_snapshot',
    'cwm_morning_briefing',
    'cwm_refresh_prices',
    'cwm_nightly_backup'
  );
exception when undefined_table then
  null;
end $$;

-- 15:00 UTC = 00:00 KST — compute snapshot
select cron.schedule(
  'cwm_daily_snapshot',
  '0 15 * * *',
  $$select public.compute_daily_snapshot((timezone('Asia/Seoul', now()))::date);$$
);

-- Hourly price refresh via Edge Function (best-effort)
select cron.schedule(
  'cwm_refresh_prices',
  '15 * * * *',
  $$select public.invoke_edge_function('refresh-prices', '{}'::jsonb);$$
);

-- 23:00 UTC = 08:00 KST — morning briefing + push
select cron.schedule(
  'cwm_morning_briefing',
  '0 23 * * *',
  $$select public.invoke_edge_function('morning-briefing', '{}'::jsonb);$$
);

-- 16:00 UTC = 01:00 KST — nightly backup
select cron.schedule(
  'cwm_nightly_backup',
  '0 16 * * *',
  $$select public.invoke_edge_function('nightly-backup', '{}'::jsonb);$$
);
