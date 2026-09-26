import pandas as pd
import pytest

from sah.schema import standardize_ohlcv, validate_ohlcv


def test_standardize_accepts_mixed_case_and_date_column():
    raw = pd.DataFrame({"Date": ["2024-01-03", "2024-01-02", "2024-01-02"], "Open": [1, 2, 2], "High": [2, 3, 3],
                        "Low": [0.5, 1, 1], "Close": [1.5, 2.5, 2.6], "Volume": ["1,000", 2000, 2000]})
    df = standardize_ohlcv(raw)
    assert list(df.columns[:5]) == ["open", "high", "low", "close", "volume"]
    assert df.index.is_monotonic_increasing and not df.index.duplicated().any()
    assert df.loc["2024-01-02", "close"] == 2.6  # keep last duplicate
    assert validate_ohlcv(df) == []


def test_standardize_missing_column_raises():
    with pytest.raises(ValueError):
        standardize_ohlcv(pd.DataFrame({"date": ["2024-01-01"], "close": [1]}))


def test_validate_detects_bad_bars(ohlcv):
    bad = ohlcv.copy()
    bad.iloc[10, bad.columns.get_loc("high")] = 0.0
    assert any("矛盾" in s for s in validate_ohlcv(bad))
