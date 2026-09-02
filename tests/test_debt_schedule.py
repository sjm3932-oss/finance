"""Amortization: 상환방법 + 대출일 → 월 원금 감소."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "streamlit_app"))

from lib.debt_schedule import (  # noqa: E402
    add_months,
    amortization_from_debt,
    build_amortization,
    equal_payment_amount,
    iter_installments,
    parse_repay_method,
    paid_installments,
    term_months,
)


def test_parse_repay_method_korean():
    assert parse_repay_method("원리금균등분할상환") == "equal_payment"
    assert parse_repay_method("원금균등") == "equal_principal"
    assert parse_repay_method("만기일시상환") == "interest_only"


def test_term_and_first_pay_date():
    start = date(2025, 5, 28)
    due = date(2075, 5, 28)
    assert term_months(start, due) == 600
    assert add_months(start, 1) == date(2025, 6, 28)
    assert add_months(start, 600) == due


def test_paid_installments_uses_payment_day():
    start = date(2020, 5, 28)
    assert paid_installments(start, date(2020, 5, 28), payment_day=28) == 0
    assert paid_installments(start, date(2020, 6, 27), payment_day=28) == 0
    assert paid_installments(start, date(2020, 6, 28), payment_day=28) == 1


def test_equal_principal_constant_principal():
    start = date(2026, 1, 1)
    due = date(2027, 1, 1)
    rows = list(
        iter_installments(
            original_principal=12_000_000,
            annual_rate_pct=0.0,
            started_on=start,
            due_date=due,
            repay_method="equal_principal",
        )
    )
    assert len(rows) == 12
    principals = [r.principal for r in rows]
    assert principals[:-1] == [1_000_000] * 11
    assert rows[-1].balance_after == 0
    assert sum(principals) == 12_000_000


def test_equal_payment_principal_rises_as_interest_falls():
    start = date(2026, 1, 15)
    due = date(2027, 1, 15)
    rows = list(
        iter_installments(
            original_principal=10_000_000,
            annual_rate_pct=6.0,
            started_on=start,
            due_date=due,
            repay_method="equal_payment",
        )
    )
    assert len(rows) == 12
    annuity = equal_payment_amount(10_000_000, 0.06 / 12, 12)
    for r in rows[:-1]:
        assert r.payment == annuity
    principals = [r.principal for r in rows]
    interests = [r.interest for r in rows]
    assert principals[0] < principals[-1]
    assert interests[0] > interests[-1]
    assert rows[-1].balance_after == 0
    assert sum(principals) == 10_000_000


def test_interest_only_zero_principal_until_maturity():
    start = date(2026, 1, 1)
    due = date(2026, 7, 1)
    rows = list(
        iter_installments(
            original_principal=100_000_000,
            annual_rate_pct=3.6,
            started_on=start,
            due_date=due,
            repay_method="interest_only",
        )
    )
    assert len(rows) == 6
    assert all(r.principal == 0 for r in rows[:-1])
    assert rows[-1].principal == 100_000_000
    assert rows[-1].balance_after == 0
    # 잔금 1억 × 3.6% / 12 = 300,000
    assert rows[0].interest == 300_000


def test_grace_then_equal_payment_holds_balance():
    start = date(2026, 1, 1)
    due = date(2027, 1, 1)
    rows = list(
        iter_installments(
            original_principal=12_000_000,
            annual_rate_pct=0.0,
            started_on=start,
            due_date=due,
            repay_method="equal_payment",
            grace_months=3,
        )
    )
    assert all(r.principal == 0 and r.in_grace for r in rows[:3])
    assert rows[2].balance_after == 12_000_000
    assert rows[-1].balance_after == 0
    assert sum(r.principal for r in rows) == 12_000_000


def test_next_month_principal_from_debt_dict():
    # 사용자 예시: 3.5억 실행, 잔금 3.25억, 4.57%, 2075-05 만기, 원리금균등
    start = date(2025, 5, 28)
    due = date(2075, 5, 28)
    plan = amortization_from_debt(
        {
            "original_principal": 350_000_000,
            "interest_rate": 4.57,
            "started_on": start.isoformat(),
            "due_date": due.isoformat(),
            "repay_method": "equal_payment",
        },
        as_of=date(2026, 9, 2),
        upcoming_n=3,
    )
    assert plan is not None
    assert plan.term == 600
    assert plan.next is not None
    assert plan.next.principal > 0
    assert plan.next.interest > plan.next.principal  # early years of a 50y mortgage
    assert plan.contracted_payment == plan.next.payment
    assert plan.next.payment == plan.next.interest + plan.next.principal


def test_missing_dates_cannot_schedule():
    assert (
        amortization_from_debt(
            {
                "original_principal": 100,
                "interest_rate": 3.5,
                "repay_method": "equal_payment",
            }
        )
        is None
    )


def test_build_amortization_paid_count():
    plan = build_amortization(
        original_principal=1_200_000,
        annual_rate_pct=0,
        started_on=date(2026, 1, 1),
        due_date=date(2027, 1, 1),
        repay_method="equal_principal",
        as_of=date(2026, 4, 1),
        upcoming_n=2,
    )
    # first pay 2026-02-01; as of Apr 1 the 3rd installment is due
    assert plan.paid == 3
    assert plan.remaining == 9
    assert plan.scheduled_balance == 900_000
    assert plan.next is not None
    assert plan.next.number == 4
