"""量能類指標：OBV、VWAP、量比、MFI。"""
from __future__ import annotations

import numpy as np
import pandas as pd


def obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["close"].diff()).fillna(0)
    return (direction * df["volume"]).cumsum()


def vwap(df: pd.DataFrame, n: int | None = None) -> pd.Series:
    """成交量加權平均價。n=None 為累積（適合日內），n 給定為滾動 n 期。"""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    pv = tp * df["volume"]
    if n is None:
        return pv.cumsum() / df["volume"].cumsum()
    return pv.rolling(n).sum() / df["volume"].rolling(n).sum()


def volume_ratio(volume: pd.Series, n: int = 20) -> pd.Series:
    """量比 = 今日量 / 前 n 日均量。>2 為明顯放量，常搭配突破確認。"""
    return volume / volume.shift(1).rolling(n).mean()


def mfi(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """資金流量指標（量加權 RSI）。"""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    mf = tp * df["volume"]
    pos = mf.where(tp > tp.shift(1), 0.0).rolling(n).sum()
    neg = mf.where(tp < tp.shift(1), 0.0).rolling(n).sum()
    return 100 - 100 / (1 + pos / neg.replace(0, np.nan))
