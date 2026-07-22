"""Korean UI labels for displayed tables (DB column → 화면 컬럼명). Tickers stay as-is."""

from __future__ import annotations

from typing import Any

import pandas as pd

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
    "increase": "증가(추가차입)",
    "repayment": "상환",
    "decrease": "감소",
    "interest": "이자원금가산",
    "other": "기타",
}
ACCOUNT_TYPE_KO = {"brokerage": "증권", "bank": "은행", "loan": "대출"}
STATUS_KO = {
    "pending": "대기",
    "approved": "승인",
    "rejected": "반려",
    "failed": "실패",
}


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
