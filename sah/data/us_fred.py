"""
FRED（聖路易聯準會）總經資料。免費。
- 不需金鑰的 CSV 端點：https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10
- 官方 API（需免費 key）：https://api.stlouisfed.org/fred/series/observations?series_id=...&api_key=...&file_type=json

常用序列：DGS10（10年美債）、DGS2、T10Y2Y（殖利率曲線）、FEDFUNDS、CPIAUCSL、UNRATE、VIXCLS、
BAMLH0A0HYM2（高收益債利差）、DTWEXBGS（美元指數）、UMCSENT（消費者信心）。
台灣總經（CPI、景氣燈號、外銷訂單）請至 主計總處/國發會 或 FinMind TaiwanBusinessIndicator。
"""
from __future__ import annotations

import io

import pandas as pd

from ..config import settings
from .base import get_client

CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
API_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_series(series_id: str, start: str | None = None) -> pd.Series:
    client = get_client()
    if settings.fred_api_key:
        params = {"series_id": series_id, "api_key": settings.fred_api_key, "file_type": "json"}
        if start:
            params["observation_start"] = start
        js = client.get_json(API_URL, params, cache_ttl=12 * 3600)
        df = pd.DataFrame(js["observations"])[["date", "value"]]
    else:
        resp = client.get(CSV_URL, {"id": series_id}, cache_ttl=12 * 3600)
        df = pd.read_csv(io.StringIO(resp.text))
        df.columns = ["date", "value"]
    s = pd.Series(pd.to_numeric(df["value"], errors="coerce").values, index=pd.to_datetime(df["date"]), name=series_id)
    s.index.name = "date"
    return s.loc[start:] if start else s
