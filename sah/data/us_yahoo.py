"""
Yahoo Finance chart API（非官方，免費，無需金鑰）。
- 端點：https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=10y&interval=1d
- 提供 adjclose（還原股利＋分割）→ 長期回測請用 adj_close。
- 台股亦可用（2330.TW、6213.TWO），可當台股備援。
- 缺點：非官方、偶爾改版或限流（回 429），生產環境不建議單獨依賴；亦可改用 yfinance 套件。
"""
from __future__ import annotations

import pandas as pd

from ..schema import standardize_ohlcv
from .base import DataSourceError, get_client

CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def fetch_daily_ohlcv(symbol: str, range_: str = "10y", interval: str = "1d",
                      start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """
    回傳標準 OHLCV，額外含 adj_close。interval 可為 1d/1wk/1mo（日內 1m/5m 僅限最近 60 天）。
    """
    params = {"interval": interval, "events": "div,splits", "includeAdjustedClose": "true"}
    if start:
        params["period1"] = int(pd.Timestamp(start).timestamp())
        params["period2"] = int(pd.Timestamp(end or pd.Timestamp.today()).timestamp()) + 86400
    else:
        params["range"] = range_
    js = get_client().get_json(CHART.format(symbol=symbol), params, headers=_HEADERS, cache_ttl=6 * 3600)
    try:
        res = js["chart"]["result"][0]
        ts = res["timestamp"]
        q = res["indicators"]["quote"][0]
        adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose", q["close"])
    except (KeyError, IndexError, TypeError) as exc:
        err = (js.get("chart") or {}).get("error")
        raise DataSourceError(f"Yahoo {symbol}: {err or '格式不符'}") from exc
    df = pd.DataFrame(
        {"date": pd.to_datetime(ts, unit="s", utc=True).tz_convert("America/New_York").normalize().tz_localize(None),
         "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"],
         "volume": q["volume"], "adj_close": adj}
    ).dropna(subset=["close"])
    return standardize_ohlcv(df)


def fetch_quote(symbols: list[str]) -> pd.DataFrame:
    """即時（延遲 15 分鐘內）報價，用 chart API range=1d 逐檔取最新一筆。"""
    rows = []
    for s in symbols:
        js = get_client().get_json(CHART.format(symbol=s), {"range": "1d", "interval": "1m"}, headers=_HEADERS)
        meta = js["chart"]["result"][0]["meta"]
        rows.append({"symbol": s, "last": meta.get("regularMarketPrice"), "prev_close": meta.get("chartPreviousClose"),
                     "currency": meta.get("currency"), "exchange": meta.get("exchangeName")})
    return pd.DataFrame(rows).set_index("symbol")
