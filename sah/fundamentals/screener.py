"""
基本面篩選器。輸入一張「每列一檔股票」的指標表，依準則回傳通過清單與各項是否通過。
預設門檻取自 docs/04；後續模型可依市場／產業覆寫。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class FundamentalCriteria:
    """None 代表不檢查該項。欄位名稱需與輸入 DataFrame 一致。"""

    max_pe: float | None = 20.0
    min_pe: float | None = 0.0
    max_pb: float | None = 3.0
    min_roe: float | None = 0.12
    min_dividend_yield: float | None = None
    min_revenue_yoy: float | None = 0.0
    max_debt_to_equity: float | None = 1.0
    min_f_score: int | None = 6
    min_fcf_yield: float | None = None
    required_columns: list[str] = field(default_factory=list)


def screen(table: pd.DataFrame, criteria: FundamentalCriteria | None = None) -> pd.DataFrame:
    """
    回傳與輸入同 index 的 DataFrame，每個檢查項目一欄 (bool)，加上 `passed`（全部通過）與 `score`（通過項目數）。
    """
    c = criteria or FundamentalCriteria()
    checks: dict[str, pd.Series] = {}

    def add(name: str, cond: pd.Series | None):
        if cond is not None:
            checks[name] = cond.fillna(False)

    if c.max_pe is not None and "pe" in table:
        add("pe_ok", (table["pe"] <= c.max_pe) & (table["pe"] > (c.min_pe if c.min_pe is not None else -1e9)))
    if c.max_pb is not None and "pb" in table:
        add("pb_ok", table["pb"] <= c.max_pb)
    if c.min_roe is not None and "roe" in table:
        add("roe_ok", table["roe"] >= c.min_roe)
    if c.min_dividend_yield is not None and "dividend_yield" in table:
        add("yield_ok", table["dividend_yield"] >= c.min_dividend_yield)
    if c.min_revenue_yoy is not None and "revenue_yoy" in table:
        add("growth_ok", table["revenue_yoy"] >= c.min_revenue_yoy)
    if c.max_debt_to_equity is not None and "debt_to_equity" in table:
        add("leverage_ok", table["debt_to_equity"] <= c.max_debt_to_equity)
    if c.min_f_score is not None and "f_score" in table:
        add("f_score_ok", table["f_score"] >= c.min_f_score)
    if c.min_fcf_yield is not None and "fcf_yield" in table:
        add("fcf_ok", table["fcf_yield"] >= c.min_fcf_yield)

    out = pd.DataFrame(checks, index=table.index)
    out["score"] = out.sum(axis=1) if not out.empty else 0
    out["passed"] = out.drop(columns=["score"]).all(axis=1) if checks else False
    return out
