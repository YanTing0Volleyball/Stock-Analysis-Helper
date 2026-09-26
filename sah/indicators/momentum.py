"""動能／擺盪類指標：KD、RSI、ROC、Williams %R。"""
from __future__ import annotations

import pandas as pd


def kd(df: pd.DataFrame, n: int = 9, k_smooth: int = 3, d_smooth: int = 3) -> pd.DataFrame:
    """
    隨機指標 KD（台股慣用 9,3,3）。
    RSV = (C - L_n) / (H_n - L_n) * 100，其中 H_n/L_n 為 n 日**最高價／最低價**（非收盤價）。
    K = 前K * (1 - 1/k_smooth) + RSV / k_smooth；D 同理。首日 K=D=50。
    回傳欄位：rsv, k, d。
    """
    low_n = df["low"].rolling(n, min_periods=n).min()
    high_n = df["high"].rolling(n, min_periods=n).max()
    rng = (high_n - low_n).replace(0, float("nan"))
    rsv = ((df["close"] - low_n) / rng * 100).fillna(50)
    k = rsv.ewm(alpha=1 / k_smooth, adjust=False).mean()
    d = k.ewm(alpha=1 / d_smooth, adjust=False).mean()
    k[low_n.isna()] = float("nan")
    d[low_n.isna()] = float("nan")
    return pd.DataFrame({"rsv": rsv.where(low_n.notna()), "k": k, "d": d})


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder RSI。>70 超買、<30 超賣；台股短線常用 6/12。"""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = gain / loss.replace(0, float("nan"))
    out = 100 - 100 / (1 + rs)
    return out.fillna(100).where(gain.notna())


def roc(close: pd.Series, n: int = 20) -> pd.Series:
    """變動率 (%)。n=252 即學術上的 12 個月動能（常搭配 skip 最近 1 個月，見 signals）。"""
    return close.pct_change(n) * 100


def williams_r(df: pd.DataFrame, n: int = 14) -> pd.Series:
    high_n = df["high"].rolling(n).max()
    low_n = df["low"].rolling(n).min()
    return (high_n - df["close"]) / (high_n - low_n).replace(0, float("nan")) * -100
