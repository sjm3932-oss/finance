"""Korean UI labels for displayed tables (DB column → 화면 컬럼명). Tickers stay as-is."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

COLUMN_KO: dict[str, str] = {
    # common
    "id": "ID",
    "ticker": "티커",
    "name": "종목명",
    "quantity": "수량",
    "qty": "수량",
    "avg_price": "평균단가",
    "avg": "평균단가",
    "price": "가격",
    "current_price": "현재가",
    "currency": "통화",
    "ccy": "통화",
    "memo": "메모",
    "reason": "사유",
    "created_at": "생성시각",
    "updated_at": "갱신시각",
    "user_id": "사용자",
    "account_id": "계좌",
    "status": "상태",
    # portfolio / dashboard
    "return_rate": "수익률(%)",
    "return_%": "수익률(%)",
    "market_value": "평가금액",
    "value": "평가금액",
    "market_value_krw": "평가금액(원)",
    "시세": "시세",
    "snapshot_date": "기준일",
    "net_assets": "순자산",
    "total_investment": "투자자산",
    "total_debt": "부채합계",
    "cash_ratio": "현금비율",
    "usdkrw": "달러원환율",
    # trades / flows
    "trade_date": "매매일",
    "trade_type": "매매구분",
    "fee": "수수료",
    "realized_pnl": "실현손익",
    "unrealized_pnl": "평가손익",
    "event_date": "발생일",
    "flow_kind": "흐름종류",
    "flow_subtype": "세부유형",
    "asset_ref": "자산/항목",
    "amount": "금액",
    "source_table": "원천테이블",
    "source_id": "원천ID",
    "recorded_at": "기록시각",
    # cash
    "flow_date": "일자",
    "flow_type": "수입지출",
    "category": "카테고리",
    # dividend
    "pay_date": "지급일",
    # debt
    "lender": "대출기관",
    "principal": "원금",
    "interest_rate": "금리(%)",
    "due_date": "만기일",
    "tx_date": "거래일",
    "tx_type": "거래유형",
    "debt_id": "부채ID",
    # tax
    "tax_year": "세무연도",
    "cum_capital_gain": "누적양도차익",
    "tax_threshold": "기본공제",
    "dividend_tax": "배당세",
    "taxable_gain": "과세대상양도차익",
    "estimated_tax": "예상세금",
    "pnl_year": "손익연도",
    "sold_qty": "매도수량",
    # staging
    "image_url": "이미지경로",
    "parsed_json": "파싱JSON",
    "uploaded_by": "업로더",
    "reviewed_by": "검토자",
    "reviewed_at": "검토시각",
    # accounts
    "institution": "금융기관",
    "account_type": "계좌유형",
    # push
    "endpoint": "엔드포인트",
    # chat
    "user_query": "질문",
    "ai_response": "답변",
}

# Money / amount columns shown in tables — format with thousand separators.
MONEY_COLUMNS: frozenset[str] = frozenset(
    {
        # English / DB
        "amount",
        "price",
        "avg_price",
        "avg",
        "fee",
        "realized_pnl",
        "unrealized_pnl",
        "market_value",
        "market_value_krw",
        "value",
        "cost",
        "principal",
        "original_principal",
        "interest_portion",
        "principal_portion",
        "balance_before",
        "balance_after",
        "balance",
        "cum_capital_gain",
        "tax_threshold",
        "dividend_tax",
        "taxable_gain",
        "estimated_tax",
        "pnl",
        "pnl_krw",
        # Korean UI
        "금액",
        "단가",
        "가격",
        "평균단가",
        "현재가",
        "평단",
        "수수료",
        "실현손익",
        "평가손익",
        "평가금액",
        "평가금액(원)",
        "평가액",
        "원금",
        "최초원금",
        "잔금",
        "납부액",
        "이자",
        "원금상환",
        "납부 전 잔금",
        "납부 후 잔금",
        "납부후잔금",
        "손익",
        "일합계",
        "합계",
        "유입",
        "유출",
        "누적양도차익",
        "기본공제",
        "배당세",
        "과세대상양도차익",
        "예상세금",
        "투자자산",
        "부채합계",
        "순자산",
    }
)

_MONEY_NAME_HINTS = (
    "금액",
    "손익",
    "원금",
    "잔금",
    "납부",
    "평가",
    "수수료",
    "단가",
    "가격",
    "평단",
    "세금",
    "공제",
    "양도",
    "amount",
    "price",
    "fee",
    "pnl",
    "principal",
    "balance",
    "value",
    "cost",
    "tax",
)
_NOT_MONEY_HINTS = (
    "율",
    "%",
    "비중",
    "수량",
    "건수",
    "비율",
    "rate",
    "qty",
    "quantity",
    "연도",
    "year",
)

FLOW_KIND_KO = {
    "trade": "매매",
    "dividend": "배당",
    "cash_flow": "현금흐름",
    "debt": "부채",
}

PNL_KIND_KO = {
    "trade_realized": "매매실현",
    "dividend": "배당",
    "interest_income": "이자수입",
    "interest_expense": "이자비용",
}

TRADE_TYPE_KO = {"buy": "매수", "sell": "매도"}
FLOW_TYPE_KO = {"income": "수입", "expense": "지출"}
DEBT_TX_KO = {
    "increase": "추가차입",
    "repayment": "원금상환",
    "decrease": "감소",
    "interest": "이자원금가산",
    "payment": "원리금 납부",
    "other": "기타",
}
ACCOUNT_TYPE_KO = {"brokerage": "증권", "bank": "은행", "loan": "대출"}
STATUS_KO = {
    "pending": "대기",
    "approved": "승인",
    "rejected": "반려",
    "failed": "실패",
}


def is_money_column(name: Any) -> bool:
    """True when a table column should show thousand separators."""
    n = str(name or "").strip()
    if not n:
        return False
    if n in MONEY_COLUMNS:
        return True
    low = n.lower()
    if any(h in n or h in low for h in _NOT_MONEY_HINTS):
        return False
    return any(h in n or h in low for h in _MONEY_NAME_HINTS)


def format_money_value(v: Any) -> str:
    """Format a scalar money value with thousand separators (1,234,567)."""
    if v is None:
        return "—"
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return "—"
        if s == "—":
            return s
        # Already display-formatted with commas or currency symbol
        if "," in s or s.startswith(("₩", "$")):
            return s
        try:
            v = float(s.replace(",", ""))
        except ValueError:
            return s
    try:
        if isinstance(v, float) and pd.isna(v):
            return "—"
        n = float(v)
    except (TypeError, ValueError):
        return "—"
    if abs(n - round(n)) < 1e-9:
        return f"{n:,.0f}"
    return f"{n:,.2f}"


def format_money_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with money columns formatted as comma-separated strings."""
    if df is None or getattr(df, "empty", True):
        return df
    out = df.copy()
    for col in out.columns:
        if not is_money_column(col):
            continue
        series = out[col]
        if pd.api.types.is_numeric_dtype(series) or series.dtype == object:
            out[col] = series.map(format_money_value)
    return out


def money_column_config(df: pd.DataFrame | list[str] | None = None) -> dict[str, Any]:
    """Streamlit NumberColumn config (thousand separators) for editable tables."""
    if df is None:
        cols: list[str] = []
    elif isinstance(df, pd.DataFrame):
        cols = [str(c) for c in df.columns]
    else:
        cols = [str(c) for c in df]
    cfg: dict[str, Any] = {}
    for c in cols:
        if is_money_column(c):
            cfg[c] = st.column_config.NumberColumn(c, format="localized")
    return cfg


def show_dataframe(df: pd.DataFrame, **kwargs: Any):
    """st.dataframe with money columns shown as 1,000-unit comma format."""
    view = format_money_columns(df)
    return st.dataframe(view, **kwargs)


def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    out = out.rename(columns={c: COLUMN_KO.get(c, c) for c in out.columns})
    return out


def map_series(series: pd.Series, mapping: dict[str, str]) -> pd.Series:
    return series.map(lambda x: mapping.get(x, x) if isinstance(x, str) else x)


def localize_flow_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "flow_kind" in df.columns:
        df["flow_kind"] = map_series(df["flow_kind"], FLOW_KIND_KO)
    if "trade_type" in df.columns:
        df["trade_type"] = map_series(df["trade_type"], TRADE_TYPE_KO)
    if "flow_type" in df.columns:
        df["flow_type"] = map_series(df["flow_type"], FLOW_TYPE_KO)
    if "tx_type" in df.columns:
        df["tx_type"] = map_series(df["tx_type"], DEBT_TX_KO)
    if "status" in df.columns:
        df["status"] = map_series(df["status"], STATUS_KO)
    if "account_type" in df.columns:
        df["account_type"] = map_series(df["account_type"], ACCOUNT_TYPE_KO)
    # subtype often like income:월급 — localize prefix
    if "flow_subtype" in df.columns:
        def _sub(v):
            if not isinstance(v, str):
                return v
            if v in TRADE_TYPE_KO:
                return TRADE_TYPE_KO[v]
            if v in DEBT_TX_KO:
                return DEBT_TX_KO[v]
            if ":" in v:
                a, b = v.split(":", 1)
                return f"{FLOW_TYPE_KO.get(a, a)}:{b}"
            return v

        df["flow_subtype"] = df["flow_subtype"].map(_sub)
    return rename_columns(df)
