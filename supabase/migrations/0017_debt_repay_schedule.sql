-- 0017_debt_repay_schedule.sql
-- 상환 방법 + 최초 대출일 so monthly principal reduction can be calculated.

alter table public.debts
  add column if not exists started_on date;

alter table public.debts
  add column if not exists repay_method text not null default 'equal_payment';

alter table public.debts
  add column if not exists monthly_payment numeric;

alter table public.debts
  add column if not exists payment_day int;

alter table public.debts
  add column if not exists grace_months int not null default 0;

alter table public.debts drop constraint if exists debts_repay_method_check;
alter table public.debts
  add constraint debts_repay_method_check
  check (repay_method in ('equal_payment', 'equal_principal', 'interest_only'));

alter table public.debts drop constraint if exists debts_payment_day_check;
alter table public.debts
  add constraint debts_payment_day_check
  check (payment_day is null or payment_day between 1 and 28);

alter table public.debts drop constraint if exists debts_grace_months_check;
alter table public.debts
  add constraint debts_grace_months_check
  check (grace_months >= 0);

comment on column public.debts.started_on is '최초 대출 실행일. With due_date, defines 상환 회차.';
comment on column public.debts.repay_method is 'equal_payment=원리금균등, equal_principal=원금균등, interest_only=만기일시.';
comment on column public.debts.monthly_payment is '약정 월 납부액. Null → compute from method/rate/term.';
comment on column public.debts.payment_day is '매월 납부일 (1–28). Null → 대출일 일자.';
comment on column public.debts.grace_months is '거치 개월. 해당 기간은 이자만, 이후 분할상환.';

create or replace function public.apply_ocr_debt_schedule()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_debt jsonb;
  v_lender text;
  v_method text;
begin
  if tg_op <> 'UPDATE' then
    return new;
  end if;
  if new.status is distinct from 'approved' then
    return new;
  end if;
  if old.status is not distinct from 'approved' then
    return new;
  end if;
  if jsonb_typeof(coalesce(new.parsed_json->'debts', '[]'::jsonb)) <> 'array' then
    return new;
  end if;

  for v_debt in
    select value from jsonb_array_elements(coalesce(new.parsed_json->'debts', '[]'::jsonb))
  loop
    v_lender := nullif(trim(coalesce(v_debt->>'lender', '')), '');
    if v_lender is null then
      continue;
    end if;

    v_method := nullif(trim(coalesce(v_debt->>'repay_method', '')), '');
    v_method := case
      when v_method in (
        'equal_payment', '원리금균등', '원리금균등분할', '원리금균등분할상환', '원리금분할'
      ) then 'equal_payment'
      when v_method in (
        'equal_principal', '원금균등', '원금균등분할', '원금균등분할상환', '원금분할'
      ) then 'equal_principal'
      when v_method in (
        'interest_only', '만기일시', '만기일시상환', '만기상환', '일시상환', '거치', '이자만'
      ) then 'interest_only'
      else null
    end;

    update public.debts d
    set
      started_on = coalesce(
        nullif(v_debt->>'started_on', '')::date,
        d.started_on
      ),
      repay_method = coalesce(v_method, d.repay_method),
      monthly_payment = coalesce(
        nullif(v_debt->>'monthly_payment', '')::numeric,
        d.monthly_payment
      ),
      payment_day = coalesce(
        nullif(v_debt->>'payment_day', '')::int,
        d.payment_day
      ),
      grace_months = coalesce(
        nullif(v_debt->>'grace_months', '')::int,
        d.grace_months
      )
    where d.lender ilike v_lender
       or v_lender ilike '%' || d.lender || '%'
       or d.lender ilike '%' || v_lender || '%';
  end loop;

  return new;
end;
$$;

drop trigger if exists trg_ocr_debt_schedule on public.ocr_staging;
create trigger trg_ocr_debt_schedule
  after update on public.ocr_staging
  for each row execute function public.apply_ocr_debt_schedule();
