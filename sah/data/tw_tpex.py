"""
櫃買中心 (TPEx，上櫃) 資料來源。免費、無需金鑰。

端點：
- 上櫃全市場即時/當日行情 https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes
- 上櫃個股日K（單月）     https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock?code=6213&date=YYYY/MM/DD&response=json
- 三大法人買賣超（日）    https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date=YYYY/MM/DD&response=json

TPEx 網站於 2024 年改版，舊 /web/ 路徑已失效；上述為改版後端點（實測 2026/09 可用）。
注意：已轉上市的股票（如 6213 聯茂）在此查詢會回空表，請改用 tw_twse。
若端點再次變動，優先改用 tw_finmind 作為備援。
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from ..schema import standardize_ohlcv
from .base import DataSourceError, get_client, to_float

BASE = "https://www.tpex.org.tw/www/zh-tw"
OPENAPI = "https://www.tpex.org.tw/openapi/v1"
_HIST_TTL = 30 * 24 * 3600


def fetch_daily_ohlcv(stock_no: str, start: str | dt.date, end: str | dt.date | None = None) -> pd.DataFrame:
    """上櫃個股日K（逐月）。"""
    start = pd.Timestamp(start).date()
    end = pd.Timestamp(end).date() if end else dt.date.today()
    client = get_client()
    frames = []
    cur = dt.date(start.year, start.month, 1)
    while cur <= end:
        js = client.get_json(
            f"{BASE}/afterTrading/tradingStock",
            {"code": stock_no, "date": cur.strftime("%Y/%m/%d"), "response": "json"},
            cache_ttl=_HIST_TTL,
        )
        tables = js.get("tables") or []
        data = tables[0].get("data", []) if tables else js.get("aaData", [])
        rows = []
        for r in data:
            # 欄位：日期(民國), 成交股數(千股), 成交金額(千元), 開盤, 最高, 最低, 收盤, 漲跌, 筆數
            y, mo, d = str(r[0]).replace("＊", "").split("/")
            rows.append(
                {
                    "date": dt.date(int(y) + 1911, int(mo), int(d)),
                    "open": to_float(r[3]),
                    "high": to_float(r[4]),
                    "low": to_float(r[5]),
                    "close": to_float(r[6]),
                    "volume": to_float(r[1]) * 1000,
                    "turnover": to_float(r[2]) * 1000,
                }
            )
        if rows:
            frames.append(pd.DataFrame(rows))
        cur = dt.date(cur.year + (cur.month // 12), cur.month % 12 + 1, 1)
    if not frames:
        raise DataSourceError(f"TPEx 無 {stock_no} 資料")
    return standardize_ohlcv(pd.concat(frames)).loc[str(start) : str(end)]


def fetch_mainboard_quotes() -> pd.DataFrame:
    """上櫃全市場當日行情（OpenAPI）。"""
    js = get_client().get_json(f"{OPENAPI}/tpex_mainboard_quotes", cache_ttl=600)
    df = pd.DataFrame(js)
    ren = {
        "SecuritiesCompanyCode": "code", "CompanyName": "name", "Close": "close", "Open": "open",
        "High": "high", "Low": "low", "TradingShares": "volume", "TransactionAmount": "turnover", "Change": "change",
    }
    df = df.rename(columns=ren)
    for c in ("close", "open", "high", "low", "volume", "turnover", "change"):
        if c in df.columns:
            df[c] = df[c].map(to_float)
    return df.set_index("code")


def fetch_institutional(date: str | dt.date) -> pd.DataFrame:
    """上櫃三大法人買賣超。欄位同 tw_twse.fetch_institutional。"""
    d = pd.Timestamp(date)
    js = get_client().get_json(
        f"{BASE}/insti/dailyTrade",
        {"type": "Daily", "sect": "EW", "date": d.strftime("%Y/%m/%d"), "response": "json"},
        cache_ttl=_HIST_TTL,
    )
    tables = js.get("tables") or []
    if not tables or not tables[0].get("data"):
        raise DataSourceError(f"TPEx insti {d.date()} 無資料")
    fields = tables[0]["fields"]
    df = pd.DataFrame(tables[0]["data"], columns=fields)

    def col(part: str) -> pd.Series:
        m = [c for c in fields if part in c and "買賣超" in c]
        return df[m[0]].map(to_float) if m else pd.Series(float("nan"), index=df.index)

    out = pd.DataFrame(
        {
            "name": df[fields[1]].str.strip(),
            "foreign_net": col("外資及陸資") if any("外資及陸資" in c and "不含" not in c for c in fields) else col("外資"),
            "trust_net": col("投信"),
            "dealer_net": col("自營商"),
            "total_net": col("合計") if any("合計" in c for c in fields) else col("三大法人"),
        }
    )
    out["code"] = df[fields[0]].str.strip()
    out["date"] = d
    return out.set_index("code")
