import numpy as np
import pandas as pd

from sah.analysis import COMPANY_COLUMNS, analyze_company


def test_analyze_company_full_row(ohlcv):
    idx = pd.period_range("2021-01", periods=40, freq="M").to_timestamp()
    rev = pd.Series(100 * 1.03 ** np.arange(40), index=idx)
    inst = pd.DataFrame({"foreign_net": 1000.0, "trust_net": 0.0, "dealer_net": 0.0, "total_net": 1000.0}, index=ohlcv.index)
    row = analyze_company(ohlcv, code="TEST", name="測試", monthly_revenue=rev, inst=inst,
                          valuation={"pe": 12, "pb": 1.5, "dividend_yield": 4})
    assert list(row) == COMPANY_COLUMNS
    assert row["revenue_signal"] == 1 and row["inst_score"] >= 1
    assert 0 <= row["composite_score"] <= 100
    assert row["action"] in {"買進", "觀察", "不動作", "續抱", "減碼", "賣出"}


def test_analyze_company_minimal(ohlcv):
    row = analyze_company(ohlcv, code="X", market="US")
    assert np.isnan(row["fundamental_score"]) and np.isnan(row["chips_score"])
    assert not np.isnan(row["composite_score"])
