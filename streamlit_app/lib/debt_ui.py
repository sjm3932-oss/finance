"""Debt views: dashboard = read-only; 기록하기 수기 = write forms."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from lib.theme import CHART_COLORS, PRIMARY, chart_layout, show_plotly
from lib.ui_ko import DEBT_TX_KO

DEBT_KIND_KO = {
    "mortgage": "주택담보",
    "credit": "신용대출",
    "card": "카드론",
    "student": "학자금",
    "jeonse": "전세자금",
    "other": "기타",
}


def _fmt(n) -> str:
    try:
        return f"₩{float(n):,.0f}"
    except (TypeError, ValueError):
        return "—"


def split_monthly_payment(balance: float, annual_rate_pct: float, payment: float) -> tuple[float, float]:
    """Split 원리금 using interest on 잔금 (monthly rate = annual/12)."""
    bal = max(float(balance or 0), 0.0)
    pay = max(float(payment or 0), 0.0)
    rate = float(annual_rate_pct or 0)
    interest = round(bal * (rate / 100.0) / 12.0)
    if pay <= interest:
        return pay, 0.0
    principal = pay - interest
    if principal > bal:
        principal = bal
        interest = pay - principal
    return float(interest), float(principal)


def _load_debts(client, account_ids: list[str] | None = None) -> list[dict]:
    try:
        rows = (
            client.table("debts")
            .select(
                "id,user_id,lender,debt_kind,principal,original_principal,"
                "interest_rate,due_date,memo,created_at,account_id"
            )
            .order("lender")
            .execute()
            .data
            or []
        )
    except Exception:
        rows = (
            client.table("debts")
            .select(
                "id,user_id,lender,debt_kind,principal,original_principal,"
                "interest_rate,due_date,memo,created_at"
            )
            .order("lender")
            .execute()
            .data
            or []
        )
    allow = {str(a) for a in account_ids} if account_ids is not None else None
    out = []
    for d in rows:
        aid = str(d.get("account_id") or "")
        if allow is not None and aid not in allow:
            continue
        d["debt_kind"] = d.get("debt_kind") or "other"
        d["original_principal"] = float(d.get("original_principal") or d.get("principal") or 0)
        d["principal"] = float(d.get("principal") or 0)
        d["interest_rate"] = float(d.get("interest_rate") or 0)
        out.append(d)
    return out


def _load_txs(client, debt_id: str, limit: int = 60) -> list[dict]:
    return (
        client.table("debt_transactions")
        .select(
            "id,tx_date,tx_type,amount,interest_portion,principal_portion,"
            "balance_before,balance_after,rate_used,memo,created_at"
        )
        .eq("debt_id", debt_id)
        .order("tx_date", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )


def render_debt_dashboard(
    client,
    *,
    account_ids: list[str] | None = None,
    account_label: str = "전체",
) -> None:
    """Read-only debt overview for the dashboard."""
    st.caption(
        "종류별 잔금·상환 현황을 조회합니다. "
        "등록·납부·이자율 변경·OCR은 「기록하기」에서만 합니다."
    )
    debts = _load_debts(client, account_ids=account_ids)
    if not debts:
        label = f"{account_label} · " if account_label and account_label != "전체" else ""
        st.info(
            f"{label}등록된 부채가 없습니다. "
            "계좌에 연결하려면 「기록하기 → 수기 → 부채」에서 계좌를 지정하세요."
            if account_ids is not None
            else "등록된 부채가 없습니다. 「기록하기 → 수기」또는 OCR로 추가하세요."
        )
        return

    total_bal = sum(d["principal"] for d in debts)
    total_orig = sum(d["original_principal"] for d in debts)
    paid = max(total_orig - total_bal, 0)
    m1, m2, m3 = st.columns(3, gap="small")
    m1.metric("총 잔금", _fmt(total_bal))
    m2.metric("최초 원금 합", _fmt(total_orig))
    m3.metric("누적 원금상환(추정)", _fmt(paid))

    ddf = pd.DataFrame(debts)
    ddf["종류"] = ddf["debt_kind"].map(lambda k: DEBT_KIND_KO.get(k, k))
    by_kind = ddf.groupby("종류", as_index=False)["principal"].sum()
    if not by_kind.empty and by_kind["principal"].sum() > 0:
        fig = px.pie(
            by_kind,
            names="종류",
            values="principal",
            color_discrete_sequence=CHART_COLORS,
            hole=0.4,
        )
        fig.update_layout(chart_layout(260, title="종류별 잔금"))
        show_plotly(fig)

    st.markdown("##### 부채 목록")
    for d in debts:
        progress = 0.0
        if d["original_principal"] > 0:
            progress = min(max(1 - d["principal"] / d["original_principal"], 0), 1)
        kind_label = DEBT_KIND_KO.get(d["debt_kind"], d["debt_kind"])
        st.markdown(
            f"**{d['lender']}** · {kind_label} · "
            f"잔금 {_fmt(d['principal'])} · 이자 {d['interest_rate']:.2f}% · "
            f"상환진행 {progress * 100:.1f}%"
        )
        st.progress(progress)

    labels = {
        d["id"]: (
            f"{DEBT_KIND_KO.get(d['debt_kind'], d['debt_kind'])} · {d['lender']} "
            f"(잔금 {_fmt(d['principal'])})"
        )
        for d in debts
    }
    pick = st.selectbox(
        "상세 조회",
        options=list(labels),
        format_func=lambda i: labels[i],
        key="debt_dash_pick",
    )
    debt = next(d for d in debts if d["id"] == pick)

    st.markdown(f"### {debt['lender']}")
    k1, k2, k3, k4 = st.columns(4, gap="small")
    k1.metric("잔금", _fmt(debt["principal"]))
    k2.metric("최초 원금", _fmt(debt["original_principal"]))
    k3.metric("연 이자율", f"{debt['interest_rate']:.2f}%")
    month_int = round(debt["principal"] * (debt["interest_rate"] / 100.0) / 12.0)
    k4.metric("이달 예상 이자", _fmt(month_int))

    hist = (
        client.table("debt_rate_history")
        .select("effective_date,interest_rate,memo")
        .eq("debt_id", debt["id"])
        .order("effective_date", desc=True)
        .limit(12)
        .execute()
        .data
        or []
    )
    if hist:
        st.caption("이자율 이력")
        st.dataframe(
            pd.DataFrame(
                {
                    "적용일": [h["effective_date"] for h in hist],
                    "이자율(%)": [h["interest_rate"] for h in hist],
                    "메모": [h.get("memo") or "" for h in hist],
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    txs = _load_txs(client, debt["id"])
    st.markdown("##### 납부·변동 이력")
    if not txs:
        st.caption("이력이 없습니다.")
        return

    rows = [
        {
            "일자": t.get("tx_date"),
            "유형": DEBT_TX_KO.get(t.get("tx_type"), t.get("tx_type")),
            "납부액": t.get("amount"),
            "이자": t.get("interest_portion"),
            "원금상환": t.get("principal_portion"),
            "적용금리(%)": t.get("rate_used"),
            "납부 전 잔금": t.get("balance_before"),
            "납부 후 잔금": t.get("balance_after"),
            "메모": t.get("memo") or "",
        }
        for t in txs
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=360)

    pay_rows = [
        t
        for t in sorted(txs, key=lambda x: x.get("tx_date") or "")
        if t.get("balance_after") is not None
    ]
    if pay_rows:
        tdf = pd.DataFrame(
            {
                "일자": [t["tx_date"] for t in pay_rows],
                "잔금": [float(t["balance_after"]) for t in pay_rows],
            }
        )
        fig2 = px.line(tdf, x="일자", y="잔금", markers=True)
        fig2.update_traces(line_color=PRIMARY)
        fig2.update_layout(chart_layout(240, title="잔금 추이"))
        show_plotly(fig2)


def render_debt_forms(client, user) -> None:
    """Write path for debts — used only under 기록하기 → 수기."""
    st.caption(
        "부채 등록 · 원리금 납부 · 이자율 변경. "
        "스크린샷은 「OCR → 부채 명세/납부」를 사용하세요."
    )
    debts = _load_debts(client)

    with st.expander("부채 등록", expanded=not debts):
        with st.form("debt_create_record"):
            lender = st.text_input("대출명/기관", placeholder="KB국민 주택담보대출")
            kind = st.selectbox(
                "종류",
                options=list(DEBT_KIND_KO.keys()),
                format_func=lambda k: DEBT_KIND_KO[k],
            )
            c1, c2 = st.columns(2)
            balance = c1.number_input("현재 잔금(원)", min_value=0.0, step=100000.0, format="%.0f")
            original = c2.number_input("최초 원금(원)", min_value=0.0, step=100000.0, format="%.0f")
            c3, c4 = st.columns(2)
            rate = c3.number_input("연 이자율(%)", min_value=0.0, step=0.1, format="%.2f", value=3.5)
            due = c4.date_input("만기일", value=date.today())
            no_due = st.checkbox("만기일 없음")
            accounts = (
                client.table("accounts").select("id,institution").order("institution").execute().data
                or []
            )
            acct_options = [None] + [a["id"] for a in accounts]
            acct_labels = {None: "(계좌 미연결)"}
            for a in accounts:
                acct_labels[a["id"]] = a.get("institution") or a["id"]
            link_account = st.selectbox(
                "연결 계좌 (선택)",
                options=acct_options,
                format_func=lambda i: acct_labels.get(i, str(i)),
                help="내 자산에서 계좌별로 부채를 보려면 연결하세요.",
            )
            memo = st.text_input("메모", "")
            if st.form_submit_button("등록", type="primary"):
                if not lender.strip():
                    st.error("대출명을 입력하세요.")
                else:
                    orig = original if original > 0 else balance
                    payload = {
                        "user_id": str(user.id),
                        "lender": lender.strip(),
                        "debt_kind": kind,
                        "principal": balance,
                        "original_principal": orig,
                        "interest_rate": rate,
                        "due_date": None if no_due else due.isoformat(),
                        "memo": memo or None,
                    }
                    if link_account:
                        payload["account_id"] = link_account
                    try:
                        row = client.table("debts").insert(payload).execute().data
                    except Exception:
                        payload.pop("account_id", None)
                        row = client.table("debts").insert(payload).execute().data
                    if row:
                        client.table("debt_rate_history").insert(
                            {
                                "debt_id": row[0]["id"],
                                "user_id": str(user.id),
                                "effective_date": date.today().isoformat(),
                                "interest_rate": rate,
                                "memo": "등록 시 이자율",
                            }
                        ).execute()
                    st.success("부채가 등록되었습니다.")
                    st.rerun()

    if not debts:
        return

    labels = {
        d["id"]: f"{d['lender']} (잔금 {_fmt(d['principal'])})"
        for d in debts
    }
    pick = st.selectbox(
        "대상 부채",
        options=list(labels),
        format_func=lambda i: labels[i],
        key="debt_form_pick",
    )
    debt = next(d for d in debts if d["id"] == pick)
    bal = debt["principal"]
    rate = debt["interest_rate"]

    st.markdown(
        f"**선택:** {debt['lender']} · 잔금 {_fmt(bal)} · {rate:.2f}% · "
        f"이달 예상 이자 {_fmt(round(bal * rate / 100 / 12))}"
    )

    with st.expander("이자율 변경", expanded=False):
        with st.form("debt_rate_change_record"):
            new_rate = st.number_input(
                "새 연 이자율(%)",
                min_value=0.0,
                value=float(rate),
                step=0.05,
                format="%.2f",
            )
            eff = st.date_input("적용일", value=date.today())
            rate_memo = st.text_input("사유", placeholder="기준금리 인상 반영")
            if st.form_submit_button("이자율 저장", type="primary"):
                client.table("debts").update({"interest_rate": new_rate}).eq("id", debt["id"]).execute()
                client.table("debt_rate_history").insert(
                    {
                        "debt_id": debt["id"],
                        "user_id": str(user.id),
                        "effective_date": eff.isoformat(),
                        "interest_rate": new_rate,
                        "memo": rate_memo or None,
                    }
                ).execute()
                st.success(f"이자율 {rate:.2f}% → {new_rate:.2f}%")
                st.rerun()

    st.markdown("##### 원리금 납부")
    with st.form("debt_payment_record"):
        c1, c2 = st.columns(2)
        payment = c1.number_input("납부 금액(원리금 합계, 원)", min_value=0.0, step=10000.0, format="%.0f")
        pay_date = c2.date_input("납부일", value=date.today())
        memo = st.text_input("메모", "")
        interest_p, principal_p = split_monthly_payment(bal, rate, payment)
        st.info(
            f"예상 분할 — 이자 {_fmt(interest_p)} · 원금 {_fmt(principal_p)} · "
            f"납부 후 잔금 {_fmt(max(bal - principal_p, 0))}"
        )
        if st.form_submit_button("납부 기록", type="primary"):
            if payment <= 0:
                st.error("납부 금액을 입력하세요.")
            else:
                interest_p, principal_p = split_monthly_payment(bal, rate, payment)
                after = max(bal - principal_p, 0)
                client.table("debt_transactions").insert(
                    {
                        "debt_id": debt["id"],
                        "user_id": str(user.id),
                        "tx_date": pay_date.isoformat(),
                        "tx_type": "payment",
                        "amount": payment,
                        "interest_portion": interest_p,
                        "principal_portion": principal_p,
                        "balance_before": bal,
                        "balance_after": after,
                        "rate_used": rate,
                        "memo": memo or "월 원리금 납부",
                    }
                ).execute()
                st.success(f"기록됨 — 잔금 {_fmt(after)}")
                st.rerun()

    with st.expander("추가 조정 (추가차입 · 원금만 상환)", expanded=False):
        with st.form("debt_adjust_record"):
            adj_type = st.selectbox(
                "유형",
                ["increase", "repayment"],
                format_func=lambda x: DEBT_TX_KO.get(x, x),
            )
            c1, c2 = st.columns(2)
            amt = c1.number_input("금액", min_value=0.0, step=10000.0, format="%.0f")
            adj_date = c2.date_input("일자", value=date.today())
            adj_memo = st.text_input("메모", "")
            if st.form_submit_button("조정 기록"):
                if amt <= 0:
                    st.error("금액을 확인하세요.")
                else:
                    client.table("debt_transactions").insert(
                        {
                            "debt_id": debt["id"],
                            "user_id": str(user.id),
                            "tx_date": adj_date.isoformat(),
                            "tx_type": adj_type,
                            "amount": amt,
                            "principal_portion": amt if adj_type == "repayment" else None,
                            "balance_before": bal,
                            "rate_used": rate,
                            "memo": adj_memo or None,
                        }
                    ).execute()
                    st.success("반영되었습니다.")
                    st.rerun()


# Back-compat alias
def render_debt_panel(client, user=None) -> None:
    render_debt_dashboard(client)
