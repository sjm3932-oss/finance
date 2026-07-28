import Link from "next/link";

const LINKS = [
  {
    title: "기록하기",
    body: "계좌 · 매매 · 배당 · 현금 · 부채 · 기타자산",
    href: "/record",
  },
  {
    title: "OCR · 승인",
    body: "스크린샷 → Edge Gemini → 검토/승인",
    href: "/ocr",
  },
  {
    title: "순자산 구성",
    body: "투자 · 현금 · 기타 · 배분 괴리",
    href: "/more/net-worth",
  },
  {
    title: "기타자산",
    body: "부동산 · 연금 · 보험 · 예적금",
    href: "/more/other-assets",
  },
  {
    title: "부채",
    body: "잔금 · 종류별 · 상세",
    href: "/more/debts",
  },
  {
    title: "관심종목",
    body: "등록 · 목표가/손절 · 알림",
    href: "/more/watchlist",
  },
  {
    title: "세금",
    body: "양도차익 입력 · 예상세",
    href: "/more/tax",
  },
  {
    title: "한투 API 동기화",
    body: "Phase 3에서 연동 예정",
  },
];

export default function MorePage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-extrabold tracking-tight">더보기</h1>
        <p className="mt-1 text-sm text-muted">
          기록 · OCR · 순자산 · 세금 · 관심종목
        </p>
      </div>
      <div className="space-y-3">
        {LINKS.map((item) => {
          const className =
            "block rounded-2xl border border-line bg-surface px-4 py-4 shadow-soft";
          const inner = (
            <>
              <div className="font-extrabold tracking-tight">{item.title}</div>
              <div className="mt-1 text-sm text-muted">{item.body}</div>
            </>
          );
          if (item.href) {
            return (
              <Link key={item.title} href={item.href} className={className}>
                {inner}
              </Link>
            );
          }
          return (
            <div key={item.title} className={className}>
              {inner}
            </div>
          );
        })}
      </div>
    </div>
  );
}
