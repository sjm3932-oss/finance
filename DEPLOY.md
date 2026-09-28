# 정석 배포 (터널 · Streamlit 금지)

클라우드 에이전트/노트북에서 `cloudflared`·`pinggy` 같은 **임시 터널**로
모바일 접속을 여는 것은 데모용입니다. 주소가 바뀌고, DNS가 사라지고,
경고 페이지가 뜨며, Google 로그인이 깨집니다.

**Streamlit Community Cloud / `*.streamlit.app` 도 더 이상 쓰지 않습니다.**  
실사용 앱은 **Vercel의 Next.js (`web/`)** 하나입니다.

## 원론적 해결

Next.js 앱을 **고정 HTTPS 호스트**에 배포하고, 그 URL 하나만
Supabase Auth Site URL / OAuth `redirect_to`에 넣습니다.

권장: **Vercel** — Production alias `https://richddoong.vercel.app`

### 1) GitHub에 코드 push

리포: `https://github.com/sjm3932-oss/finance`  
프로덕션 브랜치: Vercel에 연결된 브랜치 (예: `cursor/wealth-mvp-core-faae` → 이후 `main`)

### 2) Vercel에 배포

1. https://vercel.com 접속 → GitHub로 로그인
2. Project: `richddoong` (Root Directory = `web`)
3. Framework: Next.js
4. Production domain: `https://richddoong.vercel.app`
5. Environment variables:

```
NEXT_PUBLIC_SUPABASE_URL=https://lsqkixysysfhywipmrky.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
ALLOWED_EMAILS=sjm3932@gmail.com,...
```

Gemini / Toss / KIS 시크릿은 **Vercel이 아니라** Supabase Edge secrets에 둡니다.

6. Deploy

### 3) Supabase Auth + app_runtime에 고정 URL 등록

```bash
.venv/bin/python scripts/set_production_url.py https://richddoong.vercel.app
```

또는 Dashboard → Authentication → URL Configuration:

- Site URL: `https://richddoong.vercel.app`
- Redirect URLs: 같은 주소, `/**`, `/auth/callback` (+ 로컬 `http://localhost:3000/**`)

`app_runtime.public_url`도 위 스크립트가 갱신합니다 (`docs/` · `public/go.html` 점프 페이지가 이 값을 읽습니다).

### 4) Google OAuth

Google Cloud Console → OAuth 클라이언트의 승인된 리디렉션 URI에
Supabase 콜백만 있으면 됩니다:

`https://lsqkixysysfhywipmrky.supabase.co/auth/v1/callback`

### 5) app-gateway (선택 북마크)

Edge `app-gateway`는 Production URL로 302 합니다. 배포:

```bash
supabase functions deploy app-gateway --project-ref lsqkixysysfhywipmrky
# optional override:
# supabase secrets set PRODUCTION_APP_URL=https://richddoong.vercel.app
```

### 6) 접속

북마크는 **오직** `https://richddoong.vercel.app`  
`*.streamlit.app` / `trycloudflare.com` / `pinggy.net` 은 쓰지 않습니다.

## 로컬 개발

```bash
cd web
cp .env.example .env.local
npm i
npm run dev
```

자세한 경로·Edge 계약: [`web/README.md`](./web/README.md)

## 왜 터널·Streamlit은 정석이 아닌가

| 방식 | 고정 URL | OAuth | 모바일 실사용 |
|------|----------|-------|----------------|
| Cloudflare/Pinggy 임시 터널 | ❌ 수시 변경/소멸 | ❌ 깨짐 | ❌ |
| Streamlit Community Cloud | ✅ (구 호스트) | 병행 시 혼선 | ❌ 폐기 |
| Vercel (Next.js `web/`) | ✅ | ✅ | ✅ |
