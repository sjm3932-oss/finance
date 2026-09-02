"""Amortization schedule from 상환방법 + 최초 대출일 + 만기."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date

REPAY_METHOD_KO = {
    "equal_payment": "원리금균등분할",
    "equal_principal": "원금균등분할",
    "interest_only": "만기일시상환",
}

# Korean bank screens → internal key
_REPAY_ALIASES = {
    "equal_payment": "equal_payment",
    "equal_principal": "equal_principal",
    "interest_only": "interest_only",
    "원리금균등": "equal_payment",
    "원리금균등분할": "equal_payment",
    "원리금균등분할상환": "equal_payment",
    "원리금분할": "equal_payment",
    "원리금 균등": "equal_payment",
    "원금균등": "equal_principal",
    "원금균등분할": "equal_principal",
    "원금균등분할상환": "equal_principal",
    "원금분할": "equal_principal",
    "원금 균등": "equal_principal",
    "만기일시": "interest_only",
    "만기일시상환": "interest_only",
    "만기상환": "interest_only",
    "일시상환": "interest_only",
    "거치": "interest_only",
    "이자만": "interest_only",
}


@dataclass(frozen=True)
class Installment:
    number: int
    pay_date: date
    payment: int
    interest: int
    principal: int
    balance_after: int
    in_grace: bool = False


@dataclass(frozen=True)
class Amortization:
    method: str
    term: int
    paid: int
    remaining: int
    contracted_payment: int
    scheduled_balance: int
    next: Installment | None
    upcoming: list[Installment]


def parse_repay_method(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "equal_payment"
    return _REPAY_ALIASES.get(raw, _REPAY_ALIASES.get(raw.replace(" ", ""), "equal_payment"))


def parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return date(y, m, min(d.day, monthrange(y, m)[1]))


def months_between(start: date, end: date) -> int:
    if end < start:
        return 0
    return (end.year - start.year) * 12 + (end.month - start.month)


def term_months(started_on: date, due_date: date) -> int:
    return max(months_between(started_on, due_date), 1)


def _won(n: float) -> int:
    return int(round(float(n)))


def equal_payment_amount(principal: float, monthly_rate: float, n: int) -> int:
    """Fixed 원리금 for n remaining amortizing months."""
    p = max(float(principal), 0.0)
    n = max(int(n), 1)
    i = float(monthly_rate)
    if i <= 0:
        return _won(p / n)
    factor = (1 + i) ** n
    return _won(p * i * factor / (factor - 1))


def _pay_day(started_on: date, payment_day: int | None) -> int:
    if payment_day and 1 <= int(payment_day) <= 28:
        return int(payment_day)
    return min(started_on.day, 28)


def paid_installments(
    started_on: date,
    as_of: date,
    *,
    payment_day: int | None = None,
) -> int:
    """How many monthly payments have come due on or before as_of (first pay = +1 month)."""
    day = _pay_day(started_on, payment_day)
    k = months_between(started_on, as_of)
    if as_of.day < day:
        k -= 1
    return max(k, 0)


def iter_installments(
    *,
    original_principal: float,
    annual_rate_pct: float,
    started_on: date,
    due_date: date,
    repay_method: str = "equal_payment",
    grace_months: int = 0,
    monthly_payment: float | None = None,
    payment_day: int | None = None,
):
    """Yield each 월 상환 from installment 1 .. n. First due date is start + 1 month."""
    method = parse_repay_method(repay_method)
    n = term_months(started_on, due_date)
    grace = min(max(int(grace_months or 0), 0), max(n - 1, 0))
    if method == "interest_only":
        grace = 0
    i = float(annual_rate_pct or 0) / 100.0 / 12.0
    balance = _won(original_principal)
    amort_n = max(n - grace, 1)
    override = _won(monthly_payment) if monthly_payment and monthly_payment > 0 else None
    annuity = override if (method == "equal_payment" and override) else equal_payment_amount(
        original_principal, i, amort_n
    )
    prin_fixed = _won(original_principal / amort_n) if amort_n else balance

    for k in range(1, n + 1):
        in_grace = method != "interest_only" and k <= grace
        pay_date = add_months(started_on, k)
        if payment_day and 1 <= int(payment_day) <= 28:
            pay_date = pay_date.replace(day=min(int(payment_day), monthrange(pay_date.year, pay_date.month)[1]))
        interest = _won(balance * i)
        last = k == n
        if method == "interest_only" or in_grace:
            principal = balance if last else 0
            payment = principal + interest
        elif method == "equal_principal":
            principal = balance if last else min(prin_fixed, balance)
            payment = principal + interest
        else:
            if last:
                principal = balance
                payment = principal + interest
            else:
                payment = annuity
                principal = payment - interest
                if principal < 0:
                    principal = 0
                    payment = interest
                if principal > balance:
                    principal = balance
                    payment = principal + interest
        balance = max(balance - principal, 0)
        yield Installment(
            number=k,
            pay_date=pay_date,
            payment=payment,
            interest=interest,
            principal=principal,
            balance_after=balance,
            in_grace=in_grace,
        )


def build_amortization(
    *,
    original_principal: float,
    annual_rate_pct: float,
    started_on: date,
    due_date: date,
    repay_method: str = "equal_payment",
    grace_months: int = 0,
    monthly_payment: float | None = None,
    payment_day: int | None = None,
    as_of: date | None = None,
    upcoming_n: int = 12,
) -> Amortization:
    as_of = as_of or date.today()
    method = parse_repay_method(repay_method)
    n = term_months(started_on, due_date)
    paid = min(paid_installments(started_on, as_of, payment_day=payment_day), n)
    upcoming: list[Installment] = []
    scheduled_balance = _won(original_principal)
    nxt: Installment | None = None
    contracted = 0
    for inst in iter_installments(
        original_principal=original_principal,
        annual_rate_pct=annual_rate_pct,
        started_on=started_on,
        due_date=due_date,
        repay_method=method,
        grace_months=grace_months,
        monthly_payment=monthly_payment,
        payment_day=payment_day,
    ):
        if inst.number <= paid:
            scheduled_balance = inst.balance_after
            continue
        if nxt is None:
            nxt = inst
            contracted = inst.payment
            scheduled_balance = inst.balance_after if paid == inst.number else scheduled_balance
        if len(upcoming) < max(int(upcoming_n), 0):
            upcoming.append(inst)
        elif nxt is not None:
            break
    if nxt is None:
        contracted = 0
    return Amortization(
        method=method,
        term=n,
        paid=paid,
        remaining=max(n - paid, 0),
        contracted_payment=contracted,
        scheduled_balance=scheduled_balance,
        next=nxt,
        upcoming=upcoming,
    )


def amortization_from_debt(debt: dict, *, as_of: date | None = None, upcoming_n: int = 12) -> Amortization | None:
    started = parse_date(debt.get("started_on"))
    due = parse_date(debt.get("due_date"))
    orig = float(debt.get("original_principal") or 0)
    if not started or not due or orig <= 0:
        return None
    if due <= started:
        return None
    mp = debt.get("monthly_payment")
    try:
        monthly = float(mp) if mp not in (None, "") else None
    except (TypeError, ValueError):
        monthly = None
    return build_amortization(
        original_principal=orig,
        annual_rate_pct=float(debt.get("interest_rate") or 0),
        started_on=started,
        due_date=due,
        repay_method=debt.get("repay_method") or "equal_payment",
        grace_months=int(debt.get("grace_months") or 0),
        monthly_payment=monthly,
        payment_day=debt.get("payment_day"),
        as_of=as_of,
        upcoming_n=upcoming_n,
    )
