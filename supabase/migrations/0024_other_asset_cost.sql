-- Purchase cost so 부동산·기타자산 can show return vs current 시세 (value_krw).

alter table public.other_assets
  add column if not exists cost_krw numeric;

comment on column public.other_assets.cost_krw is '매수가(원). Null = unknown; 시세는 value_krw';
comment on column public.other_assets.value_krw is '현재 시세/평가액(원)';
