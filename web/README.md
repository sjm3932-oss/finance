# 부자뚱 Web (Next.js) — Phase 0

Streamlit과 **병행**하는 Next.js UI입니다. Supabase Auth/DB는 그대로 쓰고,
Phase 0에서는 **로그인 + 순자산/보유 읽기**만 제공합니다.

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

Site URL은 배포 후 Next 고정 URL로 맞추거나, Streamlit과 병행 시
둘 다 Redirect allow-list에 넣습니다.

## Vercel 배포 (권장)

1. 루트 디렉터리를 `web` 로 지정
2. Environment variables:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `ALLOWED_EMAILS`
   - `NEXT_PUBLIC_STREAMLIT_URL` (선택)

## Phase 0 범위

- [x] App Router + 디자인 토큰 (부자뚱 그린)
- [x] Google OAuth + allow-list
- [x] 하단 네비 (요약 / 보유 / 더보기)
- [x] 순자산·보유 읽기 전용
- [ ] 기록/승인/한투 API → 이후 Phase
