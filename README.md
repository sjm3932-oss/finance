# 부자뚱 (Couples Wealth Master)

부부 공동 자산 관리 시스템 (Sovereign) — MVP 코어 루프.

**Supabase:** https://lsqkixysysfhywipmrky.supabase.co

> **모바일/실사용 배포:** 임시 터널(Cloudflare/Pinggy)은 쓰지 마세요.  
> 고정 URL이 필요합니다 → [`DEPLOY.md`](./DEPLOY.md).

## UI (병행)

| 앱 | 경로 | 상태 |
|----|------|------|
| **Next.js (신규)** | [`web/`](./web/) | Phase 0: 로그인 + 순자산/보유 읽기 |
| **Streamlit** | `streamlit_app/` | 기록(OCR/수기)·승인·챗 등 기존 기능 |

Next 로컬: `cd web && cp .env.example .env.local && npm i && npm run dev`  
자세한 내용: [`web/README.md`](./web/README.md)

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

### Dummy demo data

After the couple user has logged in once, replace OCR uploads / sparse ledger rows with a rich demo dataset (accounts, trades with realized P&L, dividends, cash flows, debt, monthly snapshots):

```bash
.venv/bin/python scripts/seed_dummy_data.py
```

This clears `ocr_staging` (+ OCR storage objects) and rebuilds transactional tables for `sjm3932@gmail.com`. Re-run anytime to reset.

### Supabase Auth

1. Enable Google provider in Authentication → Providers
2. Set Site URL / Redirect URLs to the **fixed Streamlit Cloud URL**:
   `https://richddoong.streamlit.app`
   (see [`DEPLOY.md`](./DEPLOY.md); do **not** use Pinggy/Cloudflare tunnels)
3. Put couple emails in `ALLOWED_EMAILS` and Streamlit Secrets
4. Bookmark only `https://richddoong.streamlit.app`

### Run

```bash
streamlit run streamlit_app/Home.py
```

Production: deploy on Streamlit Community Cloud — do not run `keep_public_tunnel.sh`.

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
  ],
  "debts": [
    {
      "lender": "KB국민 주택담보대출",
      "debt_kind": "mortgage",
      "balance": 177000000,
      "interest_rate": 3.8,
      "due_date": "2045-06-30"
    }
  ],
  "debt_payments": [
    {
      "pay_date": "2026-07-01",
      "lender": "KB국민 주택담보대출",
      "amount": 1200000,
      "interest_portion": null,
      "principal_portion": null,
      "balance_after": 176500000
    }
  ]
}
```

Approving a staging row fires `commit_ocr_staging` (BEFORE UPDATE trigger).
Debt OCR matches `lender` to existing loans (or creates one); payments without interest/principal split are auto-split from **잔금 × 금리 ÷ 12**.

## Scheduling / Push / Backup (phases 7–8)

pg_cron jobs (KST):

| Job | Schedule | Action |
|---|---|---|
| `cwm_daily_snapshot` | 00:00 | `compute_daily_snapshot()` |
| `cwm_refresh_prices` | hourly :15 | Edge `refresh-prices` |
| `cwm_morning_briefing` | 08:00 | Edge `morning-briefing` (Gemini + Web Push) |
| `cwm_nightly_backup` | 01:00 | Edge `nightly-backup` → Storage `backups/` (7-day retention) |

In the app: **Notifications** page to subscribe to Web Push and run jobs manually.

Function secrets (set via `supabase secrets set`): `GEMINI_API_KEY`, `VAPID_*`, `PUBLIC_APP_URL`.

## Daily per-asset snapshots

`holding_daily_snapshots` stores each holding’s quantity/price/value every day (KST).
`compute_daily_snapshot()` writes both aggregate `daily_snapshots` and per-ticker rows.
Dashboard charts total + per-asset trends and supports date/ticker drill-down.
