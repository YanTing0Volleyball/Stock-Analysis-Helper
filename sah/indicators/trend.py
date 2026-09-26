"""趨勢類指標：均線、MACD、ADX。"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    """簡單移動平均。台股常用 5/10/20/60/120/240（月/季/半年/年線）；美股常用 20/50/200。"""
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    """指數移動平均（adjust=False，與多數看盤軟體一致）。"""
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def wma(s: pd.Series, n: int) -> pd.Series:
    w = np.arange(1, n + 1, dtype=float)
    return s.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """回傳 DataFrame: macd（DIF）、signal（DEA/MACD 線）、hist（柱狀 = DIF - DEA）。"""
    dif = ema(close, fast) - ema(close, slow)
    dea = dif.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": dif, "signal": dea, "hist": dif - dea})


def _true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    return pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()], axis=1
    ).max(axis=1)


def adx(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    """
    平均趨向指標 (Wilder)。回傳 plus_di, minus_di, adx。
    ADX > 25 視為有趨勢（適合順勢指標）；< 20 為盤整（適合 KD/RSI 逆勢）。
    """
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr = _true_range(df)
    alpha = 1.0 / n
    atr_ = tr.ewm(alpha=alpha, adjust=False, min_periods=n).mean()
    plus_di = 100 * plus_dm.ewm(alpha=alpha, adjust=False, min_periods=n).mean() / atr_
    minus_di = 100 * minus_dm.ewm(alpha=alpha, adjust=False, min_periods=n).mean() / atr_
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_ = dx.ewm(alpha=alpha, adjust=False, min_periods=n).mean()
    return pd.DataFrame({"plus_di": plus_di, "minus_di": minus_di, "adx": adx_})
