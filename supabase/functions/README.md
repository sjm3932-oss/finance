# Edge Functions: OCR + Wealth Chat

Gemini calls run **inside Supabase Edge Functions**, not on Vercel.
Next.js only uploads files / shows UI and invokes Functions with the user JWT.

## Functions

| Name | Path | Role |
|------|------|------|
| `ocr-parse` | `supabase/functions/ocr-parse` | Storage image → Gemini Vision → `ocr_staging` |
| `wealth-chat` | `supabase/functions/wealth-chat` | Rebuild wealth context → Gemini → `ai_chat_logs` |
| Shared | `supabase/functions/_shared/gemini.ts` | CORS, auth, Gemini REST helpers |

## Deploy (one-time / when code changes)

```bash
# From repo root, with supabase CLI logged in
supabase secrets set GEMINI_API_KEY=... GEMINI_MODEL=gemini-2.5-flash

supabase functions deploy ocr-parse
supabase functions deploy wealth-chat
```

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
  "history": [{ "role": "user|model", "content": "..." }]
}
```

Response: `{ ok, reply, meta }`

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
