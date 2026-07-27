"""Other assets, cash balances, ownership tags, allocation targets UI."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from lib.net_worth import (
    ALLOC_CAT_KO,
    ASSET_KIND_KO,
    OWNERSHIP_KO,
    allocation_actual,
    allocation_drift,
    load_accounts_enriched,
    load_allocation_targets,
    load_other_assets,
)
from lib.ui_ko import show_dataframe
from lib.ux import fmt_krw, section_header


def _schema_ready(client) -> bool:
    try:
        client.table("other_assets").select("id").limit(1).execute()
        return True
    except Exception:
        return False


def render_ownership_badge(ownership: str | None) -> str:
    return OWNERSHIP_KO.get(ownership or "joint", "공동")


def render_allocation_drift(client, nw: dict) -> None:
    targets = load_allocation_targets(client)
    if not any(targets.values()):
        st.caption("목표 배분이 없습니다. 「기록하기 → 수기 → 순자산」에서 설정하세요.")
        return
    actual = allocation_actual(nw)
    rows = allocation_drift(actual, targets)
    disp = pd.DataFrame(
        {
            "구분": [r["label"] for r in rows],
            "현재(%)": [round(r["actual_pct"], 1) for r in rows],
            "목표(%)": [round(r["target_pct"], 1) for r in rows],
            "괴리(%p)": [round(r["drift_pct"], 1) for r in rows],
        }
    )
    show_dataframe(disp, use_container_width=True, hide_index=True)
    biggest = max(rows, key=lambda r: abs(r["drift_pct"]))
    if abs(biggest["drift_pct"]) >= 5:
        direction = "초과" if biggest["drift_pct"] > 0 else "부족"
        st.info(
            f"가장 큰 괴리: **{biggest['label']}** {direction} "
            f"{abs(biggest['drift_pct']):.1f}%p "
            f"(현재 {biggest['actual_pct']:.1f}% / 목표 {biggest['target_pct']:.1f}%)"
        )
    total_t = sum(targets.values())
    if abs(total_t - 100) > 0.5:
        st.warning(f"목표 비중 합계가 {total_t:.0f}%입니다. 100%에 맞추는 것을 권장합니다.")


def render_other_assets_dashboard(client, nw: dict) -> None:
    section_header("기타 자산", "부동산 · 연금 · 보험 · 예적금 등")
    if not _schema_ready(client):
        st.info(
            "기타 자산 테이블이 아직 없습니다. "
            "`supabase/migrations/0017_net_worth_wealth.sql` 을 적용하세요."
        )
        return
    rows = load_other_assets(client)
    if not rows:
        st.caption("등록된 기타 자산이 없습니다. 「기록하기 → 수기 → 순자산」에서 추가하세요.")
        return
    disp = pd.DataFrame(
        {
            "이름": [r.get("name") for r in rows],
            "종류": [ASSET_KIND_KO.get(r.get("asset_kind"), r.get("asset_kind")) for r in rows],
            "평가액": [r.get("value_krw") for r in rows],
            "소유": [OWNERSHIP_KO.get(r.get("ownership"), "공동") for r in rows],
            "메모": [r.get("memo") or "" for r in rows],
        }
    )
    show_dataframe(disp, use_container_width=True, hide_index=True)
    st.caption(f"기타 자산 합계 {fmt_krw(nw.get('other'))}")


def render_cash_accounts_panel(client) -> None:
    section_header("계좌 현금 · 소유", "예수금/현금잔고와 공동·개인 태그")
    accounts = load_accounts_enriched(client)
    if not accounts:
        st.caption("계좌가 없습니다.")
        return
    has_cash_col = any("cash_balance" in a for a in accounts)
    disp = pd.DataFrame(
        {
            "금융기관": [a.get("institution") for a in accounts],
            "유형": [a.get("account_type") for a in accounts],
            "통화": [a.get("currency") for a in accounts],
            "현금잔고": [a.get("cash_balance", 0) for a in accounts],
            "소유": [
                OWNERSHIP_KO.get(a.get("ownership", "joint"), "공동") for a in accounts
            ],
        }
    )
    show_dataframe(disp, use_container_width=True, hide_index=True)
    if not has_cash_col:
        st.caption("현금잔고/소유 컬럼은 마이그레이션 0017 적용 후 활성화됩니다.")


def render_wealth_forms(client, user) -> None:
    """Manual forms: other assets, cash balances, ownership, allocation targets."""
    st.caption("순자산 구성: 기타자산 · 계좌 현금 · 소유 태그 · 목표 배분")
    if not _schema_ready(client):
        st.warning(
            "DB 마이그레이션 `0017_net_worth_wealth.sql` 이 필요합니다. "
            "적용 전에도 증권·부채 기반 순자산 추정은 홈에서 동작합니다."
        )

    tabs = st.tabs(["기타자산", "계좌 현금·소유", "목표 배분"])

    with tabs[0]:
        _form_other_assets(client, user)
    with tabs[1]:
        _form_account_cash_ownership(client)
    with tabs[2]:
        _form_allocation_targets(client)


def _form_other_assets(client, user) -> None:
    if not _schema_ready(client):
        return
    rows = load_other_assets(client)
    if rows:
        show_dataframe(
            pd.DataFrame(
                {
                    "ID": [r["id"] for r in rows],
                    "이름": [r.get("name") for r in rows],
                    "종류": [
                        ASSET_KIND_KO.get(r.get("asset_kind"), r.get("asset_kind"))
                        for r in rows
                    ],
                    "평가액": [r.get("value_krw") for r in rows],
                    "소유": [
                        OWNERSHIP_KO.get(r.get("ownership"), "공동") for r in rows
                    ],
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    with st.form("other_asset_create"):
        name = st.text_input("이름", placeholder="강남 아파트 / IRP / 종신보험")
        kind = st.selectbox(
            "종류",
            options=list(ASSET_KIND_KO.keys()),
            format_func=lambda k: ASSET_KIND_KO[k],
        )
        value = st.number_input("평가액(원)", min_value=0.0, step=1_000_000.0, format="%.0f")
        ownership = st.selectbox(
            "소유",
            options=list(OWNERSHIP_KO.keys()),
            format_func=lambda k: OWNERSHIP_KO[k],
        )
        memo = st.text_input("메모", "")
        if st.form_submit_button("추가", type="primary"):
            if not name.strip():
                st.error("이름을 입력하세요.")
            else:
                try:
                    client.table("other_assets").insert(
                        {
                            "user_id": str(user.id),
                            "name": name.strip(),
                            "asset_kind": kind,
                            "value_krw": value,
                            "ownership": ownership,
                            "memo": memo or None,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ).execute()
                    st.success("추가됨")
                    st.rerun()
                except Exception as e:
                    st.error(f"저장 실패: {e}")

    if rows:
        with st.form("other_asset_update"):
            options = {r["id"]: f"{r.get('name')} ({fmt_krw(r.get('value_krw'))})" for r in rows}
            pick = st.selectbox(
                "수정/삭제할 항목",
                options=list(options),
                format_func=lambda i: options[i],
            )
            cur = next(r for r in rows if r["id"] == pick)
            new_val = st.number_input(
                "평가액(원) 수정",
                min_value=0.0,
                value=float(cur.get("value_krw") or 0),
                step=100_000.0,
                format="%.0f",
            )
            c1, c2 = st.columns(2)
            save = c1.form_submit_button("평가액 저장", type="primary")
            delete = c2.form_submit_button("삭제")
            if save:
                client.table("other_assets").update(
                    {
                        "value_krw": new_val,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                ).eq("id", pick).execute()
                st.success("수정됨")
                st.rerun()
            if delete:
                client.table("other_assets").delete().eq("id", pick).execute()
                st.success("삭제됨")
                st.rerun()


def _form_account_cash_ownership(client) -> None:
    accounts = load_accounts_enriched(client)
    if not accounts:
        st.info("먼저 계좌를 만드세요 (OCR 탭).")
        return
    for a in accounts:
        aid = a["id"]
        with st.form(f"acct_cash_{aid}"):
            st.markdown(f"**{a.get('institution')}** · {a.get('account_type')} · {a.get('currency')}")
            try:
                cash_default = float(a.get("cash_balance") or 0)
            except (TypeError, ValueError):
                cash_default = 0.0
            cash = st.number_input(
                "현금/예수금",
                min_value=0.0,
                value=cash_default,
                step=10000.0,
                format="%.0f",
                key=f"cash_input_{aid}",
            )
            own_opts = list(OWNERSHIP_KO.keys())
            cur_own = a.get("ownership") or "joint"
            if cur_own not in own_opts:
                cur_own = "joint"
            ownership = st.selectbox(
                "소유",
                options=own_opts,
                index=own_opts.index(cur_own),
                format_func=lambda k: OWNERSHIP_KO[k],
                key=f"own_input_{aid}",
            )
            if st.form_submit_button("저장", type="primary"):
                try:
                    client.table("accounts").update(
                        {"cash_balance": cash, "ownership": ownership}
                    ).eq("id", aid).execute()
                    st.success("저장됨")
                    st.rerun()
                except Exception as e:
                    st.error(
                        f"저장 실패 (마이그레이션 0017 필요 여부 확인): {e}"
                    )


def _form_allocation_targets(client) -> None:
    targets = load_allocation_targets(client)
    with st.form("alloc_targets_form"):
        vals = {}
        cols = st.columns(4)
        for i, cat in enumerate(("domestic", "overseas", "cash", "other")):
            with cols[i]:
                vals[cat] = st.number_input(
                    ALLOC_CAT_KO[cat],
                    min_value=0.0,
                    max_value=100.0,
                    value=float(targets.get(cat) or 0),
                    step=1.0,
                    format="%.0f",
                )
        st.caption(f"합계 {sum(vals.values()):.0f}% (권장 100%)")
        if st.form_submit_button("목표 저장", type="primary"):
            try:
                for cat, pct in vals.items():
                    client.table("allocation_targets").upsert(
                        {
                            "category": cat,
                            "target_pct": pct,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ).execute()
                st.success("목표 배분 저장됨")
                st.rerun()
            except Exception as e:
                st.error(f"저장 실패: {e}")
