"use client";

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
          금융기관 이름과 통화 코드를 직접 입력하세요. 미리 정해진 증권사 목록은
          없습니다.
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
