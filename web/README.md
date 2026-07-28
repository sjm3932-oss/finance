# 부자뚱 Web (Next.js) — Phase 0 + 1

Streamlit과 **병행**하는 Next.js UI입니다. Supabase Auth/DB는 그대로 씁니다.

- **Phase 0**: 로그인 + 순자산/보유 읽기
- **Phase 1**: 읽기 UX 보강 (월 요약, 배분 괴리, 필터, 기타자산·순자산 상세)

## 로컬 실행

```bash
cd web
cp .env.example .env.local
# NEXT_PUBLIC_SUPABASE_ANON_KEY, ALLOWED_EMAILS 채우기
npm install
npm run dev
```

http://localhost:3000

## Supabase Auth 설정

Google provider의 Redirect URL에 추가:

- `http://localhost:3000/auth/callback`
- 배포 URL 예: `https://<vercel-app>.vercel.app/auth/callback`

## Vercel 배포 (권장)

1. 루트 디렉터리 `web`
2. Production Branch: `cursor/wealth-mvp-core-faae` (또는 main 머지 후)
3. Environment variables:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `ALLOWED_EMAILS`
   - `NEXT_PUBLIC_STREAMLIT_URL` (선택)

## 화면

| 경로 | 내용 |
|------|------|
| `/` | 홈 — 순자산, 월 요약, 배분 괴리, 추이, 보유 미리보기 |
| `/holdings` | 보유 전체 + 소유/계좌 필터 |
| `/more/net-worth` | 순자산 구성 · 현금 계좌 · 기타자산 |
| `/more/other-assets` | 기타자산 단독 |

## Phase 체크리스트

- [x] Phase 0: Auth + NW/보유 읽기
- [x] Phase 1: 월 요약 · 배분 괴리 · 필터 · 알림 표시 · 순자산/기타자산 상세 · 추이
- [ ] Phase 2: 기록/OCR을 Next로
- [ ] Phase 3: 한투 API
- [ ] Phase 4+: 챗/승인/Streamlit 종료
