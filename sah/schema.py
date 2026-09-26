"""
標準資料結構定義。所有模組間傳遞的價量資料都必須符合這裡的欄位規範，
後續開發（量化交易程式／手機 APP 後端）只需依此介面對接。
"""
from __future__ import annotations

from enum import Enum

import pandas as pd

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


class Market(str, Enum):
    """市場代碼。TW = 台灣上市/上櫃；US = 美國。"""

    TW = "TW"
    US = "US"


def standardize_ohlcv(df: pd.DataFrame, *, tz_naive: bool = True) -> pd.DataFrame:
    """
    將任意來源的價量表整理成標準格式：
    - index：DatetimeIndex（升冪、不重複、名稱 'date'）
    - columns：open, high, low, close, volume（float64；volume 為「股數」）
    - 額外欄位（如 turnover、adj_close）會保留在後面

    參數
    ----
    df : 需含有 date 欄或 DatetimeIndex，以及 OHLCV 欄（大小寫不拘）。
    """
    out = df.copy()
    out.columns = [str(c).strip().lower().replace(" ", "_") for c in out.columns]
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"])
        out = out.set_index("date")
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    if tz_naive and out.index.tz is not None:
        out.index = out.index.tz_localize(None)
    out.index.name = "date"

    alias = {"adj close": "adj_close", "adjclose": "adj_close", "vol": "volume", "turnover_value": "turnover"}
    out = out.rename(columns=alias)
    missing = [c for c in OHLCV_COLUMNS if c not in out.columns]
    if missing:
        raise ValueError(f"缺少必要欄位: {missing}")
    for c in OHLCV_COLUMNS + [c for c in ("adj_close", "turnover") if c in out.columns]:
        if out[c].dtype == object:
            out[c] = out[c].astype(str).str.replace(",", "", regex=False).str.strip()
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out[~out.index.duplicated(keep="last")].sort_index()
    ordered = OHLCV_COLUMNS + [c for c in out.columns if c not in OHLCV_COLUMNS]
    return out[ordered]


def validate_ohlcv(df: pd.DataFrame) -> list[str]:
    """回傳資料品質問題清單（空清單代表通過）。供回測前檢查。"""
    issues: list[str] = []
    if df.empty:
        return ["資料為空"]
    if df[OHLCV_COLUMNS].isna().any().any():
        issues.append("含 NaN 價量")
    bad = (df["high"] < df["low"]) | (df["high"] < df[["open", "close"]].max(axis=1)) | (
        df["low"] > df[["open", "close"]].min(axis=1)
    )
    if bad.any():
        issues.append(f"{int(bad.sum())} 根 K 棒 high/low 與 open/close 矛盾")
    if (df["close"] <= 0).any():
        issues.append("含非正收盤價")
    if not df.index.is_monotonic_increasing:
        issues.append("日期未排序")
    return issues
