# 부자뚱 Web (Next.js)

## 하단 탭
**홈 · 보유 · 손익 · 거래 · 더보기** (+ 플로팅 `AI` → 채팅; 기록은 더보기)

## 주요 경로
| 경로 | 내용 |
|------|------|
| `/` `/holdings` `/pnl` `/flows` | 읽기 · 차트 |
| `/record` | 수기 입력 |
| `/ocr` `/ocr/review` | OCR 업로드 · 승인 (Edge `ocr-parse`) |
| `/chat` | 자산 챗 (Edge `wealth-chat`) |
| `/more/*` | 순자산 · 기타 · 부채 · 관심 · 세금 |

## Edge Functions
See [`supabase/functions/README.md`](../supabase/functions/README.md).

```bash
supabase secrets set GEMINI_API_KEY=...
supabase functions deploy ocr-parse
supabase functions deploy wealth-chat
```

Do **not** put `GEMINI_API_KEY` in Vercel.
