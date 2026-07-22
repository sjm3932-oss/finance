# Couples Wealth Master

부부 공동 자산 관리 시스템 (Sovereign) — MVP 코어 루프.

**Supabase:** https://lsqkixysysfhywipmrky.supabase.co

## MVP 범위 (기획서 1~4단계)

1. PostgreSQL 스키마 + RLS + OCR 커밋 트리거
2. Google OAuth + `ALLOWED_EMAILS` allow-list
3. 스크린샷 업로드 → Gemini Vision → `ocr_staging`
4. 검토/승인 UI → `trades` / `holdings` 자동 반영

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, GEMINI_API_KEY, ALLOWED_EMAILS
```

### Database migrations

Target project: `lsqkixysysfhywipmrky`

```bash
# Option A — access token
export SUPABASE_ACCESS_TOKEN=...   # https://supabase.com/dashboard/account/tokens
./scripts/apply_migrations.sh

# Option B — direct Postgres URL
export SUPABASE_DB_URL='postgresql://postgres.[PASSWORD]@db.lsqkixysysfhywipmrky.supabase.co:5432/postgres'
./scripts/apply_migrations.sh

# Option C — SQL Editor
./scripts/build_combined_migration.sh
# Paste supabase/combined_migration.sql into the SQL editor
```

Then seed allow-list emails (SQL editor):

```sql
insert into public.allowed_emails (email) values
  ('you@example.com'),
  ('spouse@example.com')
on conflict do nothing;
```

### Supabase Auth

1. Enable Google provider in Authentication → Providers
2. Add redirect URL `http://localhost:8501` (and production URL)
3. Put couple emails in `ALLOWED_EMAILS`

### Run

```bash
streamlit run streamlit_app/app.py
```

## parsed_json contract

```json
{
  "account_id": "uuid",
  "trades": [
    {
      "trade_date": "YYYY-MM-DD",
      "ticker": "AAPL",
      "name": "Apple",
      "trade_type": "buy",
      "price": 190.5,
      "quantity": 10,
      "reason": ""
    }
  ],
  "holdings_snapshot": [
    {
      "ticker": "AAPL",
      "name": "Apple",
      "quantity": 10,
      "avg_price": 180,
      "currency": "USD"
    }
  ]
}
```

Approving a staging row fires `commit_ocr_staging` (BEFORE UPDATE trigger).
