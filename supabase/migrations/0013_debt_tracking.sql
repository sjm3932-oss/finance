-- Debt tracking: kinds, original principal, rate history, 원리금 payment split
-- debts.principal = 잔금 (remaining balance). Interest accrues on this balance.

alter table public.debts
  add column if not exists debt_kind text not null default 'mortgage';

alter table public.debts
  add column if not exists original_principal numeric;

update public.debts
set original_principal = coalesce(original_principal, principal)
where original_principal is null;

alter table public.debts
  alter column original_principal set default 0;

comment on column public.debts.principal is '잔금 (remaining balance). Interest is calculated on this, not original principal.';
comment on column public.debts.original_principal is '최초 원금';
comment on column public.debts.interest_rate is '현재 연 이자율 (%). Changeable; history in debt_rate_history.';

create table if not exists public.debt_rate_history (
  id uuid primary key default gen_random_uuid(),
  debt_id uuid not null references public.debts(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,
  effective_date date not null,
  interest_rate numeric not null,
  memo text,
  created_at timestamptz not null default now()
);

create index if not exists idx_debt_rate_hist_debt
  on public.debt_rate_history(debt_id, effective_date desc);

alter table public.debt_rate_history enable row level security;
drop policy if exists couple_all_debt_rate_history on public.debt_rate_history;
create policy couple_all_debt_rate_history on public.debt_rate_history
  for all to authenticated
  using (public.is_couple_member())
  with check (
    public.is_couple_member()
    and user_id in (select id from public.users)
  );

grant select, insert, update, delete on public.debt_rate_history to authenticated;

-- Seed rate history from current debts (once)
insert into public.debt_rate_history (debt_id, user_id, effective_date, interest_rate, memo)
select d.id, d.user_id, coalesce(d.created_at::date, current_date), d.interest_rate, '초기 이자율'
from public.debts d
where not exists (
  select 1 from public.debt_rate_history h where h.debt_id = d.id
);

alter table public.debt_transactions
  add column if not exists interest_portion numeric;

alter table public.debt_transactions
  add column if not exists principal_portion numeric;

alter table public.debt_transactions
  add column if not exists balance_before numeric;

alter table public.debt_transactions
  add column if not exists balance_after numeric;

alter table public.debt_transactions
  add column if not exists rate_used numeric;

alter table public.debt_transactions drop constraint if exists debt_transactions_tx_type_check;
alter table public.debt_transactions
  add constraint debt_transactions_tx_type_check
  check (tx_type in ('increase', 'decrease', 'repayment', 'interest', 'payment', 'other'));

-- Apply debt transaction to 잔금 (principal column)
create or replace function public.apply_debt_transaction()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  delta numeric;
begin
  if tg_op = 'INSERT' then
    delta := case new.tx_type
      when 'increase' then new.amount
      when 'interest' then new.amount  -- capitalize (legacy)
      when 'decrease' then -new.amount
      when 'repayment' then -new.amount
      when 'payment' then -coalesce(new.principal_portion, 0)  -- 원리금: only principal reduces 잔금
      else 0
    end;
    update public.debts
      set principal = greatest(principal + delta, 0)
      where id = new.debt_id;
    return new;
  elsif tg_op = 'DELETE' then
    delta := case old.tx_type
      when 'increase' then -old.amount
      when 'interest' then -old.amount
      when 'decrease' then old.amount
      when 'repayment' then old.amount
      when 'payment' then coalesce(old.principal_portion, 0)
      else 0
    end;
    update public.debts
      set principal = greatest(principal + delta, 0)
      where id = old.debt_id;
    return old;
  end if;
  return null;
end;
$$;

drop trigger if exists trg_apply_debt_transaction on public.debt_transactions;
create trigger trg_apply_debt_transaction
  after insert or delete on public.debt_transactions
  for each row execute function public.apply_debt_transaction();
