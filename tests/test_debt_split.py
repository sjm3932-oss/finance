"""Unit tests for debt payment split (잔금 기준) and HTML5 number step."""

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "streamlit_app"))

from lib.debt_ui import RATE_INPUT_STEP, WON_INPUT_STEP, split_monthly_payment  # noqa: E402


def html5_step_valid(value: float, min_value: float, step: float) -> bool:
    """HTML5: (value - min) must be a multiple of step (same rule Chrome and Safari use)."""
    if step <= 0:
        return True
    n = round((float(value) - float(min_value)) / float(step))
    return abs(min_value + n * step - value) < 1e-6

_DEBT_UI = Path(__file__).resolve().parents[1] / "streamlit_app" / "lib" / "debt_ui.py"


def test_split_uses_balance_not_original():
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


def test_html5_step_100000_is_why_safari_rejects_real_balance():
    # 325047983 is a valid number. It fails ONLY because step=100000.
    # Safari: "유효한 값을 입력하십시오."  Chrome also names 325000000 / 325100000.
    balance = 325_047_983
    assert not html5_step_valid(balance, 0, 100_000)
    assert html5_step_valid(325_000_000, 0, 100_000)
    assert html5_step_valid(325_100_000, 0, 100_000)
    assert html5_step_valid(balance, 0, WON_INPUT_STEP)
    assert WON_INPUT_STEP == 1


def test_html5_coarse_rate_step_rejects_two_decimal_rate():
    assert not html5_step_valid(4.57, 0.0, 0.1)
    assert html5_step_valid(4.57, 0.0, RATE_INPUT_STEP)


def _number_input_steps(source: str) -> list[tuple[str, ast.AST]]:
    tree = ast.parse(source)
    found: list[tuple[str, ast.AST]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "number_input":
            label = ""
            if node.args and isinstance(node.args[0], ast.Constant):
                label = str(node.args[0].value)
            step = None
            for kw in node.keywords:
                if kw.arg == "step":
                    step = kw.value
            found.append((label, step))
    return found


def test_won_amounts_stay_number_inputs_with_step_one():
    src = _DEBT_UI.read_text()
    assert "won_number_input" in src
    assert "won_text_input" not in src
    assert "def parse_won" not in src
    steps = _number_input_steps(src)
    assert steps
    for label, step_node in steps:
        assert step_node is not None, label
        if "이자율" in label:
            assert isinstance(step_node, ast.Name) and step_node.id == "RATE_INPUT_STEP"
        elif not label or "원" in label or label == "금액":
            assert isinstance(step_node, ast.Name) and step_node.id == "WON_INPUT_STEP", label
        else:
            assert isinstance(step_node, ast.Constant) and step_node.value == 1, label


def test_debt_form_requires_start_and_due_dates():
    src = _DEBT_UI.read_text()
    assert '"대출 시작일"' in src
    assert '"만기일"' in src
    assert "만기일 없음" not in src
    assert "최초 대출일 모름" not in src


if __name__ == "__main__":
    test_split_uses_balance_not_original()
    test_split_underpayment_all_interest()
    test_split_caps_principal_at_balance()
    test_html5_step_100000_is_why_safari_rejects_real_balance()
    test_html5_coarse_rate_step_rejects_two_decimal_rate()
    test_won_amounts_stay_number_inputs_with_step_one()
    test_debt_form_requires_start_and_due_dates()
    print("ok")
