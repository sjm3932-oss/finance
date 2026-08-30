import Link from "next/link";
import { AccountForms } from "@/components/record/AccountForms";
import { WealthForms } from "@/components/record/WealthForms";
import { FlowForms } from "@/components/record/FlowForms";
import { DebtForms } from "@/components/record/DebtForms";
import { TossSyncPanel } from "@/components/TossSyncPanel";
import { HankookSyncPanel } from "@/components/HankookSyncPanel";
import { loadPortfolioSnapshot } from "@/lib/data";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

const TABS = [
  { id: "toss", label: "토스 동기화" },
  { id: "hankook", label: "한투 동기화" },
  { id: "account", label: "계좌" },
  { id: "wealth", label: "부동산·기타" },
  { id: "flows", label: "매매·배당" },
  { id: "debt", label: "부채" },
] as const;

type TabId = (typeof TABS)[number]["id"];

async function loadDebtsFull() {
  const supabase = await createClient();
  try {
    const { data } = await supabase
      .from("debts")
      .select("id,lender,principal,interest_rate,debt_kind,due_date,ownership")
      .order("lender");
    return data || [];
  } catch {
    return [];
  }
}

export default async function RecordPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  const sp = await searchParams;
  const tab = (TABS.some((t) => t.id === sp.tab) ? sp.tab : "account") as TabId;

  const { accounts, otherAssets } = await loadPortfolioSnapshot();
  const debts = await loadDebtsFull();

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-extrabold tracking-tight">기록</h1>
        <p className="mt-1 text-sm text-muted">
          증권 동기화 · 수기 입력 · OCR은{" "}
          <Link href="/ocr" className="font-semibold text-brand">
            /ocr
          </Link>
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {TABS.map((t) => {
          const active = tab === t.id;
          return (
            <Link
              key={t.id}
              href={`/record?tab=${t.id}`}
              className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                active
                  ? "bg-brand text-white"
                  : "bg-surface text-muted ring-1 ring-line"
              }`}
            >
              {t.label}
            </Link>
          );
        })}
      </div>

      {tab === "toss" ? <TossSyncPanel /> : null}
      {tab === "hankook" ? <HankookSyncPanel /> : null}
      {tab === "wealth" ? (
        <WealthForms otherAssets={otherAssets} accounts={accounts} />
      ) : null}
      {tab === "flows" ? <FlowForms accounts={accounts} /> : null}
      {tab === "debt" ? <DebtForms debts={debts} accounts={accounts} /> : null}
      {tab === "account" ? <AccountForms accounts={accounts} /> : null}
    </div>
  );
}
