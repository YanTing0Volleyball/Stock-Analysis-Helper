"""波動類指標：布林通道、ATR、Keltner、歷史波動率。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .trend import ema, sma


def bbands(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    """布林通道。回傳 mid, upper, lower, bandwidth（(上-下)/中，衡量擠壓）、pct_b（價格在通道位置 0~1）。"""
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std(ddof=0)
    upper, lower = mid + k * sd, mid - k * sd
    return pd.DataFrame(
        {"mid": mid, "upper": upper, "lower": lower, "bandwidth": (upper - lower) / mid,
         "pct_b": (close - lower) / (upper - lower).replace(0, np.nan)}
    )


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """平均真實區間 (Wilder)。用於停損距離（如 2×ATR）與波動度調整部位。"""
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def keltner(df: pd.DataFrame, n: int = 20, atr_n: int = 10, mult: float = 2.0) -> pd.DataFrame:
    mid = ema(df["close"], n)
    a = atr(df, atr_n)
    return pd.DataFrame({"mid": mid, "upper": mid + mult * a, "lower": mid - mult * a})


def historical_volatility(close: pd.Series, n: int = 20, periods_per_year: int = 252) -> pd.Series:
    """年化歷史波動率（對數報酬標準差）。"""
    lr = np.log(close / close.shift(1))
    return lr.rolling(n).std() * np.sqrt(periods_per_year)
