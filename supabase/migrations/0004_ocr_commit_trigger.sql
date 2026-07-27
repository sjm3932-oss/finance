-- 0004_ocr_commit_trigger.sql
-- When ocr_staging.status becomes 'approved', commit trades + holdings.

create or replace function public.commit_ocr_staging()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_account_id uuid;
  v_trade jsonb;
  v_holding jsonb;
  v_created_by uuid;
begin
  if tg_op <> 'UPDATE' then
    return new;
  end if;

  if new.status is distinct from 'approved' then
    return new;
  end if;

  -- Only run on transition into approved
  if old.status is not distinct from 'approved' then
    return new;
  end if;

  v_account_id := nullif(new.parsed_json->>'account_id', '')::uuid;
  if v_account_id is null then
    raise exception 'ocr_staging.parsed_json.account_id is required';
  end if;

  if not exists (select 1 from public.accounts a where a.id = v_account_id) then
    raise exception 'account_id % not found', v_account_id;
  end if;

  v_created_by := coalesce(new.reviewed_by, new.uploaded_by);

  -- Insert trades
  if jsonb_typeof(coalesce(new.parsed_json->'trades', '[]'::jsonb)) = 'array' then
    for v_trade in
      select value from jsonb_array_elements(coalesce(new.parsed_json->'trades', '[]'::jsonb))
    loop
      insert into public.trades (
        account_id,
        trade_date,
        ticker,
        trade_type,
        price,
        quantity,
        reason,
        created_by
      ) values (
        v_account_id,
        coalesce((v_trade->>'trade_date')::date, current_date),
        v_trade->>'ticker',
        v_trade->>'trade_type',
        coalesce((v_trade->>'price')::numeric, 0),
        coalesce((v_trade->>'quantity')::numeric, 0),
        v_trade->>'reason',
        v_created_by
      );
    end loop;
  end if;

  -- Upsert holdings snapshot (optional)
  if jsonb_typeof(coalesce(new.parsed_json->'holdings_snapshot', '[]'::jsonb)) = 'array' then
    for v_holding in
      select value from jsonb_array_elements(coalesce(new.parsed_json->'holdings_snapshot', '[]'::jsonb))
    loop
      insert into public.holdings (
        account_id,
        ticker,
        name,
        quantity,
        avg_price,
        currency,
        updated_at
      ) values (
        v_account_id,
        v_holding->>'ticker',
        v_holding->>'name',
        coalesce((v_holding->>'quantity')::numeric, 0),
        coalesce((v_holding->>'avg_price')::numeric, 0),
        coalesce(v_holding->>'currency', 'KRW'),
        now()
      )
      on conflict (account_id, ticker) do update
      set
        name = excluded.name,
        quantity = excluded.quantity,
        avg_price = excluded.avg_price,
        currency = excluded.currency,
        updated_at = now();
    end loop;
  end if;

  new.reviewed_at := coalesce(new.reviewed_at, now());
  return new;
end;
$$;

drop trigger if exists trg_commit_ocr_staging on public.ocr_staging;
create trigger trg_commit_ocr_staging
  before update on public.ocr_staging
  for each row
  execute function public.commit_ocr_staging();
