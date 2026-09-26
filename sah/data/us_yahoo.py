"""
Yahoo Finance chart API（非官方，免費，無需金鑰）。
- 2024 年起需先取得 cookie 與 crumb，否則回 429/401；本模組自動處理（fc.yahoo.com → getcrumb → query2）。
- 端點：https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?range=10y&interval=1d&crumb=...
- 提供 adjclose（還原股利＋分割）→ 長期回測請用 adj_close。
- 台股亦可用（2330.TW、6488.TWO），可當台股備援。
- 缺點：非官方、偶爾改版或限流；生產環境不建議單獨依賴，亦可改用 yfinance 套件。
"""
from __future__ import annotations

import time

import pandas as pd
import requests

from ..config import settings
from ..schema import standardize_ohlcv
from .base import DataSourceError, PermanentError

CHART = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

_session: requests.Session | None = None
_crumb: str | None = None
_crumb_time = 0.0


def _get_session() -> tuple[requests.Session, str]:
    """建立帶 cookie 的 session 並取得 crumb（每 30 分鐘更新）。"""
    global _session, _crumb, _crumb_time
    if _session is None or time.time() - _crumb_time > 1800:
        s = requests.Session()
        s.headers["User-Agent"] = _UA
        s.get("https://fc.yahoo.com", timeout=settings.timeout)  # 回 404 但會設 cookie
        r = s.get("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=settings.timeout)
        if r.status_code != 200 or not r.text or "<" in r.text:
            raise DataSourceError(f"Yahoo crumb 取得失敗: HTTP {r.status_code}")
        _session, _crumb, _crumb_time = s, r.text.strip(), time.time()
    return _session, _crumb


def _get_json(url: str, params: dict, retries: int = 3) -> dict:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            s, crumb = _get_session()
            r = s.get(url, params={**params, "crumb": crumb}, timeout=settings.timeout)
            if r.status_code == 429:
                raise DataSourceError("HTTP 429 (rate limited)")
            if r.status_code == 404:
                raise PermanentError(f"Yahoo 無此代號（可能已下市或未收錄）: {url}")
            if r.status_code in (401, 403):
                global _session
                _session = None  # 強制重新取得 crumb
                raise DataSourceError(f"HTTP {r.status_code} (crumb 失效)")
            r.raise_for_status()
            return r.json()
        except PermanentError:
            raise
        except (requests.RequestException, DataSourceError, ValueError) as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise DataSourceError(f"Yahoo 請求失敗: {url}") from last


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
    js = _get_json(CHART.format(symbol=symbol), params)
    try:
        res = js["chart"]["result"][0]
        ts = res["timestamp"]
        q = res["indicators"]["quote"][0]
        adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose", q["close"])
        tz = res["meta"].get("exchangeTimezoneName", "America/New_York")
    except (KeyError, IndexError, TypeError) as exc:
        err = (js.get("chart") or {}).get("error")
        raise DataSourceError(f"Yahoo {symbol}: {err or '格式不符'}") from exc
    df = pd.DataFrame(
        {"date": pd.to_datetime(ts, unit="s", utc=True).tz_convert(tz).normalize().tz_localize(None),
         "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"],
         "volume": q["volume"], "adj_close": adj}
    ).dropna(subset=["close"])
    return standardize_ohlcv(df)


def fetch_quote(symbols: list[str]) -> pd.DataFrame:
    """延遲報價（chart meta），逐檔取最新一筆。"""
    rows = []
    for s in symbols:
        js = _get_json(CHART.format(symbol=s), {"range": "1d", "interval": "1d"})
        meta = js["chart"]["result"][0]["meta"]
        rows.append({"symbol": s, "last": meta.get("regularMarketPrice"), "prev_close": meta.get("chartPreviousClose"),
                     "currency": meta.get("currency"), "exchange": meta.get("exchangeName")})
    return pd.DataFrame(rows).set_index("symbol")
