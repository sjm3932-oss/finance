# 부자뚱 Web (Next.js) — Phase 0–2a

Streamlit과 **병행**하는 Next.js UI입니다. Supabase Auth/DB는 그대로 씁니다.

- **Phase 0**: 로그인 + 순자산/보유 읽기
- **Phase 1**: 읽기 UX 보강 (월 요약, 배분 괴리, 필터, 기타자산·순자산 상세)
- **Phase 2a**: 수기 기록 (순자산·매매·배당·현금·부채·계좌) — OCR/승인은 Streamlit

## 로컬 실행

```bash
cd web
cp .env.example .env.local
# NEXT_PUBLIC_SUPABASE_ANON_KEY, ALLOWED_EMAILS 채우기
npm install
npm run dev
```

http://localhost:3000

## 화면

| 경로 | 내용 |
|------|------|
| `/` | 홈 — 순자산, 월 요약, 배분 괴리, 추이 |
| `/holdings` | 보유 전체 |
| `/record` | 수기 기록 (순자산 / 매매·배당 / 부채 / 계좌) |
| `/more/net-worth` | 순자산 구성 |
| `/more/other-assets` | 기타자산 |

하단 탭: **홈 · 보유 · 기록 · 더보기**

## Phase 체크리스트

- [x] Phase 0: Auth + NW/보유 읽기
- [x] Phase 1: 월 요약 · 배분 괴리 · 필터 · 알림 · 상세
- [x] Phase 2a: 수기 폼
- [ ] Phase 2b–c: OCR 업로드 + 승인
- [ ] Phase 3: 한투 API
- [ ] Phase 4+: 챗 / Streamlit 종료
