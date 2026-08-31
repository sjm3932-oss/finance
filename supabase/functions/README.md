# Edge Functions: OCR + Wealth Chat

Gemini calls run **inside Supabase Edge Functions**, not on Vercel.
Next.js only uploads files / shows UI and invokes Functions with the user JWT.

## Functions

| Name | Path | Role |
|------|------|------|
| `ocr-parse` | `supabase/functions/ocr-parse` | Storage image → Gemini Vision → `ocr_staging` |
| `wealth-chat` | `supabase/functions/wealth-chat` | Rebuild wealth context → Gemini → `ai_chat_logs` |
| `toss-sync` | `supabase/functions/toss-sync` | Toss Open API holdings/trades → queue |
| `kis-sync` | `supabase/functions/kis-sync` | KIS (한투) holdings/trades/dividends → queue |
| Shared | `supabase/functions/_shared/gemini.ts` | CORS, auth, Gemini REST helpers |

## Deploy (cloud only — no laptop)

1. Create a token at https://supabase.com/dashboard/account/tokens
2. Put it in Cursor environment secrets as `SUPABASE_ACCESS_TOKEN`, **or** GitHub repo Actions secret with the same name
3. Cloud Agent can then run `supabase functions deploy toss-sync --project-ref lsqkixysysfhywipmrky` (and `kis-sync`)
4. Or GitHub Actions: workflow `Deploy Edge Functions` (`.github/workflows/deploy-functions.yml`)

`TOSS_CLIENT_ID` / `TOSS_CLIENT_SECRET` are Edge Function secrets (already in the project). They are not a substitute for deploying the function code.

Platform already injects `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`.

## API contracts

### `POST /functions/v1/ocr-parse`
Auth: user Bearer JWT

```json
{
  "image_path": "{user_id}/{stamp}_{uuid}_{filename}",
  "account_id": "uuid|null",
  "doc_type": "auto|holdings|trades|dividends|debt",
  "mime_type": "image/png"
}
```

Response: `{ ok, staging_id, status, image_url, parsed_json, error_msg }`

### `POST /functions/v1/wealth-chat`
Auth: user Bearer JWT

```json
{
  "message": "우리 순자산이 얼마야?",
  "history": [{ "role": "user|model", "content": "..." }],
  "light": false
}
```

- `light: true` or non-empty `history` → skip live Yahoo/news/search; DB cache only (faster follow-ups).
- Model returns short reply + `FOLLOWUPS:` block; API exposes `followups[]`.

Response: `{ ok, reply, followups, sources, meta }`

### `POST /functions/v1/toss-sync`
Auth: user Bearer JWT  
Secrets: `TOSS_CLIENT_ID`, `TOSS_CLIENT_SECRET`

```json
{}
```

Response: `{ ok, queued, job_id }` — Edge only enqueues. A static-IP cloud
worker (`scripts/toss_sync_worker.py`) calls Toss Open API. See
`infra/toss-sync/cloud-init.sh`.

### `POST /functions/v1/kis-sync`
Auth: user Bearer JWT

Same contract as `toss-sync`. Worker reads `KIS_APP_KEY`, `KIS_APP_SECRET`,
`KIS_CANO` (or `KIS_ACCOUNTS`) and writes `accounts` / `holdings` / `trades` /
`dividends`. Heartbeat still uses `toss_sync_worker` (same VM).

## Next.js routes

| Route | Purpose |
|-------|---------|
| `/ocr` | Upload → Storage → `ocr-parse` |
| `/ocr/review` | Edit JSON · approve/reject (DB trigger commits) |
| `/chat` | Conversational UI → `wealth-chat` |

## Security notes

- **Never** put `GEMINI_API_KEY` in Vercel env for these features.
- OCR paths must start with `{auth.uid()}/`.
- Approve still uses RLS user client; `commit_ocr_staging` trigger does the writes.
- Edge handlers use `requireCoupleUser` (JWT + `email_is_allowed` / `allowed_emails`).
  Empty `allowed_emails` denies everyone (migration `0018_tighten_email_allowlist.sql`).
- Chat context still uses the service role after the allow-list gate.
