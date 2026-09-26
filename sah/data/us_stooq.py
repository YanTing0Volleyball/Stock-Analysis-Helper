"""
Stooq 免費日K CSV（https://stooq.com），無需金鑰，作為 Yahoo 備援。
- 端點：https://stooq.com/q/d/l/?s=aapl.us&i=d  （台股：2330.tw）
- 價格為分割還原但未含股利還原；每日有下載次數上限（約數百次），超過會回「Exceeded the daily hits limit」。
"""
from __future__ import annotations

import io

import pandas as pd

from ..schema import standardize_ohlcv
from .base import DataSourceError, get_client


def fetch_daily_ohlcv(symbol: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    params = {"s": symbol.lower(), "i": "d"}
    if start:
        params["d1"] = pd.Timestamp(start).strftime("%Y%m%d")
    if end:
        params["d2"] = pd.Timestamp(end).strftime("%Y%m%d")
    resp = get_client().get("https://stooq.com/q/d/l/", params, cache_ttl=12 * 3600)
    text = resp.text
    if "Exceeded" in text or "No data" in text or not text.strip():
        raise DataSourceError(f"Stooq {symbol}: {text[:80]}")
    df = pd.read_csv(io.StringIO(text))
    return standardize_ohlcv(df)
