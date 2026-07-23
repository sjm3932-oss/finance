"""Unit tests for debt payment split (잔금 기준)."""

from streamlit_app.lib.debt_ui import split_monthly_payment


def test_split_uses_balance_not_original():
    # 잔금 1억, 연 3.6% → 월 이자 300,000
    interest, principal = split_monthly_payment(100_000_000, 3.6, 1_000_000)
    assert interest == 300_000
    assert principal == 700_000


def test_split_underpayment_all_interest():
    interest, principal = split_monthly_payment(100_000_000, 3.6, 100_000)
    assert interest == 100_000
    assert principal == 0


def test_split_caps_principal_at_balance():
    interest, principal = split_monthly_payment(500_000, 3.6, 2_000_000)
    assert principal == 500_000
    assert interest == 1_500_000
