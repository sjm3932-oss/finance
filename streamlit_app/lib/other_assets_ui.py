"""Other assets, cash balances, ownership tags, allocation targets UI."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from lib.net_worth import (
    ALLOC_CAT_KO,
    ASSET_KIND_KO,
    ASSET_KIND_KO_ALL,
    DEPOSIT_KIND_KO,
    OWNERSHIP_KO,
    allocation_actual,
    allocation_drift,
    deposit_balance,
    installment_progress,
    load_accounts_enriched,
    load_allocation_targets,
    load_deposits,
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


def _deposits_ready(client) -> bool:
    try:
        client.table("deposits").select("id").limit(1).execute()
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


def render_other_assets_dashboard(
    client,
    nw: dict | None = None,
    *,
    ownership_filter: str | None = None,
    standalone: bool = False,
) -> None:
    """기타 자산 현황. standalone=True면 전용 메뉴용 요약+목록."""
    if standalone:
        section_header("기타 자산 현황", "부동산 · 연금 · 보험 · 암호화폐 등")
    else:
        section_header("기타 자산", "부동산 · 연금 · 보험 등")

    if not _schema_ready(client):
        st.info(
            "기타 자산 테이블이 아직 없습니다. "
            "`supabase/migrations/0017_net_worth_wealth.sql` 을 적용하세요."
        )
        return

    rows = load_other_assets(client)
    rows = [r for r in rows if str(r.get("asset_kind") or "") != "deposit"]
    if ownership_filter in ("joint", "mine", "spouse"):
        rows = [r for r in rows if (r.get("ownership") or "joint") == ownership_filter]

    if not rows:
        empty = "등록된 기타 자산이 없습니다. 「기록하기 → 수기 → 순자산」에서 추가하세요."
        if ownership_filter:
            empty = "이 소유 구분의 기타 자산이 없습니다."
        st.caption(empty)
        return

    total = 0.0
    by_kind: dict[str, float] = {}
    by_own: dict[str, float] = {}
    for r in rows:
        try:
            v = float(r.get("value_krw") or 0)
        except (TypeError, ValueError):
            v = 0.0
        total += v
        kind = str(r.get("asset_kind") or "other")
        by_kind[kind] = by_kind.get(kind, 0.0) + v
        own = str(r.get("ownership") or "joint")
        by_own[own] = by_own.get(own, 0.0) + v

    if standalone:
        m1, m2, m3 = st.columns(3)
        m1.metric("기타 자산 합계", fmt_krw(total))
        m2.metric("종목 수", f"{len(rows)}건")
        top_kind = max(by_kind.items(), key=lambda x: x[1]) if by_kind else None
        m3.metric(
            "최대 비중",
            ASSET_KIND_KO_ALL.get(top_kind[0], top_kind[0]) if top_kind else "—",
            delta=fmt_krw(top_kind[1]) if top_kind else None,
            delta_color="off",
        )
        kind_disp = pd.DataFrame(
            {
                "종류": [ASSET_KIND_KO_ALL.get(k, k) for k in by_kind],
                "평가액": list(by_kind.values()),
                "비중(%)": [
                    round(100.0 * v / total, 1) if total else 0.0 for v in by_kind.values()
                ],
            }
        ).sort_values("평가액", ascending=False)
        st.markdown("##### 종류별 합계")
        show_dataframe(kind_disp, use_container_width=True, hide_index=True)

        if not ownership_filter and len(by_own) > 1:
            own_disp = pd.DataFrame(
                {
                    "소유": [OWNERSHIP_KO.get(k, k) for k in by_own],
                    "평가액": list(by_own.values()),
                }
            ).sort_values("평가액", ascending=False)
            st.markdown("##### 소유별 합계")
            show_dataframe(own_disp, use_container_width=True, hide_index=True)

    if standalone:
        st.markdown("##### 상세 목록")
    disp = pd.DataFrame(
        {
            "이름": [r.get("name") for r in rows],
            "종류": [ASSET_KIND_KO_ALL.get(r.get("asset_kind"), r.get("asset_kind")) for r in rows],
            "평가액": [r.get("value_krw") for r in rows],
            "소유": [OWNERSHIP_KO.get(r.get("ownership"), "공동") for r in rows],
            "메모": [r.get("memo") or "" for r in rows],
        }
    )
    try:
        disp = disp.sort_values("평가액", ascending=False, na_position="last")
    except Exception:
        pass
    show_dataframe(disp, use_container_width=True, hide_index=True)
    if not standalone:
        shown = nw.get("other") if nw else total
        st.caption(f"기타 자산 합계 {fmt_krw(shown if shown is not None else total)}")
    else:
        st.caption("수정·추가는 「기록하기 → 수기 → 순자산」에서 할 수 있습니다.")


def render_cash_accounts_panel(client) -> None:
    section_header("증권 예수금", "토스·한투 동기화 잔고 (수기 입력 없음)")
    accounts = []
    for a in load_accounts_enriched(client):
        try:
            if float(a.get("cash_balance") or 0) != 0:
                accounts.append(a)
        except (TypeError, ValueError):
            continue
    if not accounts:
        st.caption("표시할 증권 예수금이 없습니다.")
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


def render_deposits_dashboard(
    client,
    nw: dict | None = None,
    *,
    ownership_filter: str | None = None,
    standalone: bool = False,
) -> None:
    if standalone:
        section_header("예적금", "월납 자동계산 · 이율 · 만기")
    else:
        section_header("예적금", "독립 카테고리")

    if not _deposits_ready(client):
        st.info("예적금 테이블이 없습니다. `0029_deposits.sql`과 `0030_deposit_monthly.sql`을 적용하세요.")
        return

    rows = load_deposits(client)
    if ownership_filter in ("joint", "mine", "spouse"):
        rows = [r for r in rows if (r.get("ownership") or "joint") == ownership_filter]
    if not rows:
        st.caption("등록된 예적금이 없습니다. 「기록하기 → 수기 → 순자산」에서 추가하세요.")
        return

    total = sum(deposit_balance(r) for r in rows)
    if standalone:
        m1, m2 = st.columns(2)
        m1.metric("예적금 합계", fmt_krw(total))
        m2.metric("건수", f"{len(rows)}건")
    progs = [installment_progress(r) for r in rows]
    disp = pd.DataFrame(
        {
            "기관": [r.get("institution") for r in rows],
            "상품": [r.get("name") for r in rows],
            "종류": [
                DEPOSIT_KIND_KO.get(r.get("deposit_kind"), r.get("deposit_kind"))
                for r in rows
            ],
            "월납/원금": [
                p["monthly"] if p else r.get("principal")
                for r, p in zip(rows, progs)
            ],
            "회차": [
                f"{int(p['payments_made'])}/{int(p['payments_total'])}" if p else "—"
                for p in progs
            ],
            "잔액": [deposit_balance(r) for r in rows],
            "이율(%)": [r.get("interest_rate") for r in rows],
            "만기": [r.get("maturity_date") for r in rows],
            "소유": [OWNERSHIP_KO.get(r.get("ownership"), "공동") for r in rows],
        }
    )
    show_dataframe(disp, use_container_width=True, hide_index=True)
    shown = nw.get("deposits") if nw else total
    st.caption(f"예적금 합계 {fmt_krw(shown if shown is not None else total)}")


def render_wealth_forms(client, user) -> None:
    """Manual forms: other assets, cash balances, ownership, allocation targets."""
    st.caption("순자산 구성: 예적금 · 기타자산 · 목표 배분")
    if not _schema_ready(client):
        st.warning(
            "DB 마이그레이션 `0017_net_worth_wealth.sql` 이 필요합니다. "
            "적용 전에도 증권·부채 기반 순자산 추정은 홈에서 동작합니다."
        )

    tabs = st.tabs(["예적금", "기타자산", "목표 배분"])

    with tabs[0]:
        _form_deposits(client, user)
    with tabs[1]:
        _form_other_assets(client, user)
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
                        ASSET_KIND_KO_ALL.get(r.get("asset_kind"), r.get("asset_kind"))
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


def _form_deposits(client, user) -> None:
    if not _deposits_ready(client):
        st.info(
            "예적금 테이블이 없습니다. 마이그레이션 `0029_deposits.sql`과 "
            "`0030_deposit_monthly.sql`을 적용하세요."
        )
        return
    rows = load_deposits(client)
    if rows:
        progs = [installment_progress(r) for r in rows]
        show_dataframe(
            pd.DataFrame(
                {
                    "기관": [r.get("institution") for r in rows],
                    "상품": [r.get("name") for r in rows],
                    "종류": [
                        DEPOSIT_KIND_KO.get(r.get("deposit_kind"), r.get("deposit_kind"))
                        for r in rows
                    ],
                    "월납/원금": [
                        p["monthly"] if p else r.get("principal")
                        for r, p in zip(rows, progs)
                    ],
                    "회차": [
                        f"{int(p['payments_made'])}/{int(p['payments_total'])}" if p else "—"
                        for p in progs
                    ],
                    "잔액": [deposit_balance(r) for r in rows],
                    "이율(%)": [r.get("interest_rate") for r in rows],
                    "만기": [r.get("maturity_date") for r in rows],
                    "소유": [
                        OWNERSHIP_KO.get(r.get("ownership"), "공동") for r in rows
                    ],
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.caption("적금·청약은 월 납입액만 넣으면 가입일부터 매월 같은 날 낸 것으로 보고 원금·단리 이자를 자동 계산합니다.")
    kind = st.selectbox(
        "종류",
        options=list(DEPOSIT_KIND_KO.keys()),
        format_func=lambda k: DEPOSIT_KIND_KO[k],
        index=list(DEPOSIT_KIND_KO.keys()).index("time"),
        key="deposit_create_kind",
    )
    monthly_kind = kind in ("installment", "subscription")
    with st.form("deposit_create"):
        institution = st.text_input("금융기관", placeholder="신한은행")
        name = st.text_input(
            "상품 이름",
            placeholder="1년 적금" if monthly_kind else "1년 정기예금",
        )
        if monthly_kind:
            monthly = st.number_input(
                "월 납입액(원)", min_value=0.0, step=10_000.0, format="%.0f"
            )
            principal = 0.0
            current = 0.0
        else:
            monthly = 0.0
            principal = st.number_input(
                "원금(원)", min_value=0.0, step=100_000.0, format="%.0f"
            )
            current = st.number_input(
                "현재 잔액(원, 0이면 원금)",
                min_value=0.0,
                step=100_000.0,
                format="%.0f",
            )
        rate = st.number_input("연 이자율(%)", min_value=0.0, step=0.1, format="%.2f")
        start = st.text_input(
            "가입일 (YYYY-MM-DD, 적금은 첫 납입일)", ""
        )
        maturity = st.text_input("만기일 (YYYY-MM-DD)", "")
        ownership = st.selectbox(
            "소유",
            options=list(OWNERSHIP_KO.keys()),
            format_func=lambda k: OWNERSHIP_KO[k],
        )
        memo = st.text_input("메모", "")
        if st.form_submit_button("추가", type="primary"):
            if not institution.strip() or not name.strip():
                st.error("금융기관과 상품 이름을 입력하세요.")
            elif monthly_kind and monthly <= 0:
                st.error("월 납입액을 입력하세요.")
            elif monthly_kind and (not start.strip() or not maturity.strip()):
                st.error("적금은 가입일(첫 납입일)과 만기일이 필요합니다.")
            else:
                payload = {
                    "user_id": str(user.id),
                    "institution": institution.strip(),
                    "name": name.strip(),
                    "deposit_kind": kind,
                    "principal": 0 if monthly_kind else principal,
                    "current_value": 0 if monthly_kind else (current if current > 0 else principal),
                    "monthly_amount": monthly if monthly_kind else 0,
                    "interest_rate": rate,
                    "start_date": start.strip() or None,
                    "maturity_date": maturity.strip() or None,
                    "ownership": ownership,
                    "memo": memo or None,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                try:
                    client.table("deposits").insert(payload).execute()
                    st.success("추가됨")
                    st.rerun()
                except Exception as e:
                    if "monthly_amount" in str(e):
                        payload.pop("monthly_amount", None)
                        try:
                            client.table("deposits").insert(payload).execute()
                            st.success("추가됨 (월납 컬럼 없음 — 0030 마이그레이션을 적용하세요)")
                            st.rerun()
                        except Exception as e2:
                            st.error(f"저장 실패: {e2}")
                    else:
                        st.error(f"저장 실패: {e}")

    if rows:
        options = {
            r["id"]: f"{r.get('institution')} {r.get('name')} ({fmt_krw(deposit_balance(r))})"
            for r in rows
        }
        pick = st.selectbox(
            "수정/삭제할 항목",
            options=list(options),
            format_func=lambda i: options[i],
            key="deposit_edit_pick",
        )
        cur = next(r for r in rows if r["id"] == pick)
        prog = installment_progress(cur)
        edit_monthly = bool(prog) or cur.get("deposit_kind") in (
            "installment",
            "subscription",
        )
        with st.form("deposit_update"):
            if edit_monthly:
                if prog:
                    st.caption(
                        f"오늘 {fmt_krw(deposit_balance(cur))} · "
                        f"{int(prog['payments_made'])}/{int(prog['payments_total'])}회 · "
                        f"만기약 {fmt_krw(prog['maturity_value'])}"
                    )
                new_monthly = st.number_input(
                    "월 납입액(원)",
                    min_value=0.0,
                    value=float(cur.get("monthly_amount") or 0),
                    step=10_000.0,
                    format="%.0f",
                )
                new_val = None
            else:
                new_monthly = 0.0
                new_val = st.number_input(
                    "현재 잔액(원)",
                    min_value=0.0,
                    value=float(deposit_balance(cur)),
                    step=100_000.0,
                    format="%.0f",
                )
            new_rate = st.number_input(
                "연 이자율(%)",
                min_value=0.0,
                value=float(cur.get("interest_rate") or 0),
                step=0.1,
                format="%.2f",
            )
            c1, c2 = st.columns(2)
            save = c1.form_submit_button("저장", type="primary")
            delete = c2.form_submit_button("삭제")
            if save:
                patch = {
                    "interest_rate": new_rate,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                if edit_monthly:
                    patch["monthly_amount"] = new_monthly
                    patch["principal"] = 0
                    patch["current_value"] = 0
                else:
                    patch["current_value"] = new_val
                    patch["monthly_amount"] = 0
                try:
                    client.table("deposits").update(patch).eq("id", pick).execute()
                    st.success("수정됨")
                    st.rerun()
                except Exception as e:
                    if "monthly_amount" in str(e):
                        patch.pop("monthly_amount", None)
                        client.table("deposits").update(patch).eq("id", pick).execute()
                        st.success("수정됨")
                        st.rerun()
                    else:
                        st.error(f"저장 실패: {e}")
            if delete:
                client.table("deposits").delete().eq("id", pick).execute()
                st.success("삭제됨")
                st.rerun()


def _form_allocation_targets(client) -> None:
    targets = load_allocation_targets(client)
    cats = ("domestic", "overseas", "cash", "deposits", "other")
    with st.form("alloc_targets_form"):
        vals = {}
        cols = st.columns(5)
        for i, cat in enumerate(cats):
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
