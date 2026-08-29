# 정석 배포 (터널 금지)

실사용 앱은 **Next.js** (`https://richddoong.vercel.app`)입니다.
Google 로그인 Site URL도 이 주소여야 합니다. Streamlit Cloud는 구 UI입니다.

클라우드 에이전트/노트북에서 `cloudflared`·`pinggy` 같은 **임시 터널**로
모바일 접속을 여는 것은 데모용입니다. 주소가 바뀌고, DNS가 사라지고,
경고 페이지가 뜨며, Google 로그인이 깨집니다.

## 원론적 해결

Streamlit 앱을 **고정 HTTPS 호스트**에 배포하고, 그 URL 하나만
Supabase Auth Site URL / OAuth `redirect_to`에 넣습니다.

권장: **Streamlit Community Cloud** (무료, `*.streamlit.app`)

### 1) GitHub에 코드 push (이미 완료되어 있으면 생략)

리포: `https://github.com/sjm3932-oss/finance`  
브랜치: `main` 또는 `cursor/wealth-mvp-core-faae`

### 2) Streamlit Cloud에 배포

1. https://share.streamlit.io 접속 → GitHub로 로그인
2. **Create app**
3. Repository: `sjm3932-oss/finance`
4. Branch: 배포할 브랜치
5. Main file path: `streamlit_app/Home.py`
6. App URL: 원하는 서브도메인 (예: `couples-wealth` → `https://couples-wealth.streamlit.app`)
7. **Advanced settings → Secrets** 에 아래 TOML 입력 (값은 `.env`에서 복사)

```toml
SUPABASE_URL = "https://lsqkixysysfhywipmrky.supabase.co"
SUPABASE_ANON_KEY = "..."
SUPABASE_SERVICE_ROLE_KEY = "..."
GEMINI_API_KEY = "..."
ALLOWED_EMAILS = "sjm3932@gmail.com"
PUBLIC_APP_URL = "https://couples-wealth.streamlit.app"
GEMINI_MODEL = "gemini-2.5-flash"
```

8. Deploy

### 3) Supabase Auth에 고정 URL 등록

배포 URL이 확정되면 로컬에서:

```bash
.venv/bin/python scripts/set_production_url.py https://couples-wealth.streamlit.app
```

또는 Dashboard → Authentication → URL Configuration:

- Site URL: `https://couples-wealth.streamlit.app`
- Redirect URLs: 같은 주소 (+ `/**` 허용 시)

### 4) Google OAuth

Google Cloud Console → OAuth 클라이언트의 승인된 리디렉션 URI에
Supabase 콜백만 있으면 됩니다 (앱 URL이 바뀌어도 동일):

`https://lsqkixysysfhywipmrky.supabase.co/auth/v1/callback`

### 5) 접속

북마크는 **오직** `https://….streamlit.app`  
`trycloudflare.com` / `pinggy.net` / `app-gateway` 는 더 이상 쓰지 않습니다.

## Next.js (Phase 0–2a, 병행)

`web/` 앱은 Vercel 등에 별도 배포합니다. Root Directory = `web`.

필수 env:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `ALLOWED_EMAILS`
- `NEXT_PUBLIC_STREAMLIT_URL` (더보기 → Streamlit 링크)

Supabase Auth → Redirect URLs에 추가:

- `http://localhost:3000/auth/callback`
- `https://<your-vercel-app>.vercel.app/auth/callback`

Streamlit과 병행 기간에는 두 앱의 callback/redirect를 모두 허용하면 됩니다.
자세한 절차: [`web/README.md`](./web/README.md)

## 대안 호스트

- Render / Fly.io / Railway: 루트의 `Dockerfile` 사용 (Streamlit)
- 커스텀 도메인이 필요하면 위 PaaS + DNS

## 왜 터널은 정석이 아닌가

| 방식 | 고정 URL | OAuth | 모바일 실사용 |
|------|----------|-------|----------------|
| Cloudflare/Pinggy 임시 터널 | ❌ 수시 변경/소멸 | ❌ 깨짐 | ❌ |
| Edge gateway + 터널 | 게이트웨이만 고정, 백엔드는 여전히 터널 | 불안 | ❌ |
| Streamlit Cloud / PaaS | ✅ | ✅ | ✅ |
