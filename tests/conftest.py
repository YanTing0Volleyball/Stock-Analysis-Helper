import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def ohlcv() -> pd.DataFrame:
    """合成 3 年日K：帶趨勢＋均值回歸雜訊的幾何隨機漫步，固定 seed 保證可重現。"""
    rng = np.random.default_rng(42)
    n = 756
    dates = pd.bdate_range("2021-01-04", periods=n)
    drift = np.concatenate([np.full(300, 0.0008), np.full(200, -0.0010), np.full(256, 0.0012)])
    rets = drift + rng.normal(0, 0.015, n)
    close = 100 * np.exp(np.cumsum(rets))
    open_ = close * (1 + rng.normal(0, 0.003, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, n)))
    vol = rng.integers(1_000_000, 5_000_000, n).astype(float)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol}, index=dates).rename_axis("date")
