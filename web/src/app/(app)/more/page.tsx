import Link from "next/link";

const LINKS = [
  {
    title: "기타자산 · 순자산 구성",
    body: "Phase 1에서 Next로 이식 예정",
  },
  {
    title: "기록하기 (OCR · 수기)",
    body: "당분간 Streamlit 앱에서 입력",
    href: process.env.NEXT_PUBLIC_STREAMLIT_URL || "https://richddoong.streamlit.app",
    external: true,
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
        <p className="mt-1 text-sm text-muted">Phase 0 플레이스홀더</p>
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
              <a
                key={item.title}
                href={item.href}
                target={item.external ? "_blank" : undefined}
                rel={item.external ? "noreferrer" : undefined}
                className={className}
              >
                {inner}
              </a>
            );
          }
          return (
            <div key={item.title} className={className}>
              {inner}
            </div>
          );
        })}
      </div>
      <p className="text-xs text-muted">
        손익·배당·거래·승인·챗은 이후 Phase에서 옮깁니다.{" "}
        <Link href="/" className="font-semibold text-brand">
          요약으로
        </Link>
      </p>
    </div>
  );
}
