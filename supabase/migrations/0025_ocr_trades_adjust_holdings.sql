-- OCR 매수·매도 체결을 보유 수량·평균단가·실현손익에 반영한다.
-- 같은 승인에 holdings_snapshot 이 있으면 스냅샷이 수량의 기준이라 체결은 원장만 남긴다.
-- 체결만 올린 경우(예: 퇴직연금 체결내역)는 보유를 가감하고, 매도 시 realized_pnl 을 계산한다.

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
  v_dividend jsonb;
  v_debt jsonb;
  v_pay jsonb;
  v_created_by uuid;
  v_has_portfolio boolean;
  v_has_debt boolean;
  v_debt_id uuid;
  v_lender text;
  v_balance numeric;
  v_orig numeric;
  v_rate numeric;
  v_old_rate numeric;
  v_pay_amt numeric;
  v_interest numeric;
  v_principal numeric;
  v_bal_before numeric;
  v_bal_after numeric;
  v_rate_used numeric;
  v_px numeric;
  v_has_holdings_snap boolean;
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

  v_created_by := coalesce(new.reviewed_by, new.uploaded_by);

  v_has_holdings_snap :=
    jsonb_typeof(coalesce(new.parsed_json->'holdings_snapshot', '[]'::jsonb)) = 'array'
    and jsonb_array_length(coalesce(new.parsed_json->'holdings_snapshot', '[]'::jsonb)) > 0;

  v_has_portfolio :=
    jsonb_typeof(coalesce(new.parsed_json->'trades', '[]'::jsonb)) = 'array'
      and jsonb_array_length(coalesce(new.parsed_json->'trades', '[]'::jsonb)) > 0
    or jsonb_typeof(coalesce(new.parsed_json->'dividends', '[]'::jsonb)) = 'array'
      and jsonb_array_length(coalesce(new.parsed_json->'dividends', '[]'::jsonb)) > 0
    or jsonb_typeof(coalesce(new.parsed_json->'holdings_snapshot', '[]'::jsonb)) = 'array'
      and jsonb_array_length(coalesce(new.parsed_json->'holdings_snapshot', '[]'::jsonb)) > 0;

  v_has_debt :=
    jsonb_typeof(coalesce(new.parsed_json->'debts', '[]'::jsonb)) = 'array'
      and jsonb_array_length(coalesce(new.parsed_json->'debts', '[]'::jsonb)) > 0
    or jsonb_typeof(coalesce(new.parsed_json->'debt_payments', '[]'::jsonb)) = 'array'
      and jsonb_array_length(coalesce(new.parsed_json->'debt_payments', '[]'::jsonb)) > 0;

  v_account_id := nullif(new.parsed_json->>'account_id', '')::uuid;

  if v_has_portfolio then
    if v_account_id is null then
      raise exception 'ocr_staging.parsed_json.account_id is required for portfolio items';
    end if;
    if not exists (select 1 from public.accounts a where a.id = v_account_id) then
      raise exception 'account_id % not found', v_account_id;
    end if;
  elsif not v_has_debt then
    raise exception 'nothing to commit: empty trades/dividends/holdings/debts/debt_payments';
  end if;

  -- Trades
  if v_account_id is not null
     and jsonb_typeof(coalesce(new.parsed_json->'trades', '[]'::jsonb)) = 'array' then
    for v_trade in
      select value from jsonb_array_elements(coalesce(new.parsed_json->'trades', '[]'::jsonb))
    loop
      insert into public.trades (
        account_id, trade_date, ticker, trade_type, price, quantity,
        fee, currency, reason, created_by, adjust_holdings
      ) values (
        v_account_id,
        coalesce((v_trade->>'trade_date')::date, current_date),
        v_trade->>'ticker',
        v_trade->>'trade_type',
        coalesce((v_trade->>'price')::numeric, 0),
        coalesce((v_trade->>'quantity')::numeric, 0),
        coalesce((v_trade->>'fee')::numeric, 0),
        coalesce(nullif(v_trade->>'currency', ''), 'USD'),
        nullif(v_trade->>'reason', ''),
        v_created_by,
        not v_has_holdings_snap
      );
    end loop;
  end if;

  -- Dividends
  if v_account_id is not null
     and jsonb_typeof(coalesce(new.parsed_json->'dividends', '[]'::jsonb)) = 'array' then
    for v_dividend in
      select value from jsonb_array_elements(coalesce(new.parsed_json->'dividends', '[]'::jsonb))
    loop
      insert into public.dividends (
        user_id, account_id, ticker, name, pay_date, amount, currency, memo
      ) values (
        v_created_by,
        v_account_id,
        v_dividend->>'ticker',
        coalesce(nullif(v_dividend->>'name', ''), v_dividend->>'ticker'),
        coalesce((v_dividend->>'pay_date')::date, current_date),
        coalesce((v_dividend->>'amount')::numeric, 0),
        coalesce(nullif(v_dividend->>'currency', ''), 'USD'),
        nullif(v_dividend->>'memo', '')
      );
    end loop;
  end if;

  -- Holdings snapshot upsert
  if v_account_id is not null
     and jsonb_typeof(coalesce(new.parsed_json->'holdings_snapshot', '[]'::jsonb)) = 'array' then
    for v_holding in
      select value from jsonb_array_elements(coalesce(new.parsed_json->'holdings_snapshot', '[]'::jsonb))
    loop
      insert into public.holdings (
        account_id, ticker, name, quantity, avg_price, currency, updated_at
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

      v_px := coalesce(
        nullif(v_holding->>'last_price', '')::numeric,
        nullif(v_holding->>'current_price', '')::numeric,
        nullif(v_holding->>'avg_price', '')::numeric
      );
      if nullif(v_holding->>'ticker', '') is not null
         and v_px is not null and v_px > 0 then
        insert into public.market_prices (ticker, price, currency, updated_at)
        values (
          v_holding->>'ticker',
          v_px,
          coalesce(nullif(v_holding->>'currency', ''), 'KRW'),
          now()
        )
        on conflict (ticker) do update
        set
          price = excluded.price,
          currency = excluded.currency,
          updated_at = now();
      end if;
    end loop;
  end if;

  -- Debt payments first (history + 잔금 via trigger)
  if jsonb_typeof(coalesce(new.parsed_json->'debt_payments', '[]'::jsonb)) = 'array' then
    for v_pay in
      select value from jsonb_array_elements(coalesce(new.parsed_json->'debt_payments', '[]'::jsonb))
    loop
      v_lender := nullif(trim(coalesce(v_pay->>'lender', '')), '');
      v_debt_id := nullif(v_pay->>'debt_id', '')::uuid;

      if v_debt_id is null and v_lender is not null then
        select d.id into v_debt_id
        from public.debts d
        where d.lender ilike v_lender
           or v_lender ilike '%' || d.lender || '%'
           or d.lender ilike '%' || v_lender || '%'
        order by
          case when d.lender = v_lender then 0 else 1 end,
          d.created_at desc
        limit 1;
      end if;

      if v_debt_id is null then
        raise exception 'debt_payment lender/debt_id not matched: %', coalesce(v_lender, '(empty)');
      end if;

      select d.principal, d.interest_rate
        into v_bal_before, v_rate_used
      from public.debts d
      where d.id = v_debt_id;

      v_pay_amt := coalesce((v_pay->>'amount')::numeric, 0);
      if v_pay_amt <= 0 then
        continue;
      end if;

      v_rate_used := coalesce(nullif(v_pay->>'rate', '')::numeric, v_rate_used, 0);
      v_interest := nullif(v_pay->>'interest_portion', '')::numeric;
      v_principal := nullif(v_pay->>'principal_portion', '')::numeric;

      if v_interest is null or v_principal is null then
        v_interest := round(greatest(v_bal_before, 0) * (v_rate_used / 100.0) / 12.0);
        if v_pay_amt <= v_interest then
          v_interest := v_pay_amt;
          v_principal := 0;
        else
          v_principal := v_pay_amt - v_interest;
          if v_principal > v_bal_before then
            v_principal := v_bal_before;
            v_interest := v_pay_amt - v_principal;
          end if;
        end if;
      end if;

      v_bal_after := coalesce(
        nullif(v_pay->>'balance_after', '')::numeric,
        greatest(v_bal_before - coalesce(v_principal, 0), 0)
      );

      insert into public.debt_transactions (
        debt_id, user_id, tx_date, tx_type, amount,
        interest_portion, principal_portion,
        balance_before, balance_after, rate_used, memo
      ) values (
        v_debt_id,
        v_created_by,
        coalesce((v_pay->>'pay_date')::date, current_date),
        'payment',
        v_pay_amt,
        v_interest,
        v_principal,
        v_bal_before,
        v_bal_after,
        v_rate_used,
        coalesce(nullif(v_pay->>'memo', ''), 'OCR 원리금 납부')
      );

      -- If statement shows ending balance, sync 잔금 to it (authoritative)
      if nullif(v_pay->>'balance_after', '') is not null then
        update public.debts
          set principal = greatest((v_pay->>'balance_after')::numeric, 0)
          where id = v_debt_id;
      end if;
    end loop;
  end if;

  -- Debt balance / rate snapshot (authoritative 잔금 when provided)
  if jsonb_typeof(coalesce(new.parsed_json->'debts', '[]'::jsonb)) = 'array' then
    for v_debt in
      select value from jsonb_array_elements(coalesce(new.parsed_json->'debts', '[]'::jsonb))
    loop
      v_lender := nullif(trim(coalesce(v_debt->>'lender', '')), '');
      if v_lender is null then
        continue;
      end if;

      v_balance := coalesce((v_debt->>'balance')::numeric, (v_debt->>'principal')::numeric);
      if v_balance is null then
        continue;
      end if;

      v_orig := coalesce(
        nullif(v_debt->>'original_principal', '')::numeric,
        v_balance
      );
      v_rate := coalesce(nullif(v_debt->>'interest_rate', '')::numeric, 0);

      select d.id, d.interest_rate into v_debt_id, v_old_rate
      from public.debts d
      where d.lender ilike v_lender
         or v_lender ilike '%' || d.lender || '%'
         or d.lender ilike '%' || v_lender || '%'
      order by
        case when d.lender = v_lender then 0 else 1 end,
        d.created_at desc
      limit 1;

      if v_debt_id is null then
        insert into public.debts (
          user_id, lender, debt_kind, principal, original_principal,
          interest_rate, due_date, memo
        ) values (
          v_created_by,
          v_lender,
          coalesce(nullif(v_debt->>'debt_kind', ''), 'other'),
          greatest(v_balance, 0),
          greatest(v_orig, 0),
          v_rate,
          nullif(v_debt->>'due_date', '')::date,
          coalesce(nullif(v_debt->>'memo', ''), 'OCR 등록')
        )
        returning id into v_debt_id;

        insert into public.debt_rate_history (
          debt_id, user_id, effective_date, interest_rate, memo
        ) values (
          v_debt_id, v_created_by, current_date, v_rate, 'OCR 등록 이자율'
        );
      else
        update public.debts
        set
          principal = greatest(v_balance, 0),
          interest_rate = case
            when nullif(v_debt->>'interest_rate', '') is not null then v_rate
            else interest_rate
          end,
          debt_kind = coalesce(nullif(v_debt->>'debt_kind', ''), debt_kind),
          due_date = coalesce(nullif(v_debt->>'due_date', '')::date, due_date),
          original_principal = coalesce(original_principal, greatest(v_orig, 0)),
          memo = coalesce(nullif(v_debt->>'memo', ''), memo)
        where id = v_debt_id;

        if nullif(v_debt->>'interest_rate', '') is not null
           and v_old_rate is distinct from v_rate then
          insert into public.debt_rate_history (
            debt_id, user_id, effective_date, interest_rate, memo
          ) values (
            v_debt_id, v_created_by, current_date, v_rate, 'OCR 이자율 갱신'
          );
        end if;
      end if;
    end loop;
  end if;

  new.reviewed_at := coalesce(new.reviewed_at, now());
  begin
    perform public.invoke_edge_function('refresh-prices', '{}'::jsonb);
  exception when others then
    null;
  end;
  return new;
end;
$$;

-- 이미 넣은 체결(adjust_holdings=false)을 보유에 반영
do $$
declare
  t record;
  h public.holdings%rowtype;
  new_qty numeric;
  new_avg numeric;
  pnl numeric;
begin
  for t in
    select *
    from public.trades
    where coalesce(adjust_holdings, true) is not true
    order by trade_date, created_at, id
  loop
    select * into h
    from public.holdings
    where account_id = t.account_id and ticker = t.ticker
    for update;

    if t.trade_type = 'buy' then
      if not found then
        insert into public.holdings (
          account_id, ticker, name, quantity, avg_price, currency, updated_at
        ) values (
          t.account_id, t.ticker, t.ticker, t.quantity, t.price,
          coalesce(t.currency, 'KRW'), now()
        );
        pnl := 0;
      else
        new_qty := h.quantity + t.quantity;
        if new_qty > 0 then
          new_avg := (h.quantity * h.avg_price + t.quantity * t.price) / new_qty;
        else
          new_avg := t.price;
        end if;
        update public.holdings
          set quantity = new_qty,
              avg_price = new_avg,
              currency = coalesce(t.currency, h.currency),
              updated_at = now()
          where id = h.id;
        pnl := coalesce(t.realized_pnl, 0);
      end if;

    elsif t.trade_type = 'sell' then
      if not found then
        raise exception 'Cannot apply sell %: no holding in account', t.ticker;
      end if;
      if h.quantity < t.quantity then
        raise exception 'Cannot apply sell %: qty % > holding %',
          t.ticker, t.quantity, h.quantity;
      end if;
      pnl := (t.price - h.avg_price) * t.quantity - coalesce(t.fee, 0);
      new_qty := h.quantity - t.quantity;
      if new_qty = 0 then
        delete from public.holdings where id = h.id;
      else
        update public.holdings
          set quantity = new_qty, updated_at = now()
          where id = h.id;
      end if;
    else
      pnl := t.realized_pnl;
    end if;

    update public.trades
      set adjust_holdings = true,
          realized_pnl = pnl
      where id = t.id;
  end loop;
end $$;
