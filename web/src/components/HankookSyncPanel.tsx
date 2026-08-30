export function HankookSyncPanel() {
  return (
    <div className="rounded-2xl border border-line bg-surface px-4 py-4 shadow-soft">
      <div className="font-extrabold tracking-tight">한투 API 동기화</div>
      <p className="mt-1 text-sm text-muted">
        한국투자증권 Open API는 휴대폰 인증 이슈로 보류입니다. 지금은 토스증권
        연동을 쓰세요.
      </p>
    </div>
  );
}
