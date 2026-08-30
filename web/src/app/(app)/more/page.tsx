import Link from "next/link";
import { TossSyncPanel } from "@/components/TossSyncPanel";

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
    body: "투자 · 현금 · 기타 · 부채",
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
    title: "세금",
    body: "양도차익 입력 · 예상세",
    href: "/more/tax",
  },
];

export default function MorePage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-extrabold tracking-tight">더보기</h1>
        <p className="mt-1 text-sm text-muted">
          하단 「토스」에서 증권 잔고를 가져올 수 있어요
        </p>
      </div>
      <TossSyncPanel />
      <div className="space-y-3">
        {LINKS.map((item) => {
          const className =
            "block rounded-2xl border border-line bg-surface px-4 py-4 shadow-soft";
          return (
            <Link
              key={item.title}
              href={item.href}
              prefetch
              className={`${className} touch-manipulation transition-transform active:scale-[0.98] active:bg-canvas`}
            >
              <div className="font-extrabold tracking-tight">{item.title}</div>
              <div className="mt-1 text-sm text-muted">{item.body}</div>
            </Link>
          );
        })}
        <div className="rounded-2xl border border-line bg-surface px-4 py-4 shadow-soft">
          <div className="font-extrabold tracking-tight">한투 API 동기화</div>
          <div className="mt-1 text-sm text-muted">
            휴대폰 인증 이슈로 보류. 토스 연동을 먼저 씁니다.
          </div>
        </div>
      </div>
    </div>
  );
}
