import { TossSyncPanel } from "@/components/TossSyncPanel";

export default function TossSyncPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-extrabold tracking-tight">토스증권 동기화</h1>
        <p className="mt-1 text-sm text-muted">
          Open API 잔고를 가져와 토스증권 계좌·보유에 반영합니다. 주문은 하지
          않습니다.
        </p>
      </div>
      <TossSyncPanel />
    </div>
  );
}
