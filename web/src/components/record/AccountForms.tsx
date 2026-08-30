"use client";

import Link from "next/link";
import { CreateAccountFields } from "@/components/record/CreateAccountFields";
import {
  AccountEditRow,
  type EditableAccount,
} from "@/components/record/AccountEditRow";
import { Panel } from "@/components/record/FormUI";

export function AccountForms({ accounts }: { accounts: EditableAccount[] }) {
  return (
    <div className="space-y-4">
      <Panel title="새 계좌 추가">
        <p className="mb-3 text-xs text-muted">
          증권·은행·대출 계좌만 여기 있습니다. 부동산·연금·보험은{" "}
          <Link href="/record?tab=wealth" className="font-semibold text-brand">
            부동산·기타 탭
          </Link>
          에서 추가하세요.
        </p>
        <CreateAccountFields submitLabel="계좌 추가" />
      </Panel>

      <Panel title={`등록된 계좌 (${accounts.length})`}>
        {!accounts.length ? (
          <p className="text-sm text-muted">아직 계좌가 없습니다.</p>
        ) : (
          <ul className="divide-y divide-line">
            {accounts.map((a) => (
              <AccountEditRow key={a.id} account={a} />
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
