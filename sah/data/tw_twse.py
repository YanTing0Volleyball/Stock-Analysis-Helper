"""
台灣證券交易所 (TWSE，上市) 資料來源。全部免費、無需金鑰。

端點（皆為官方公開 JSON）：
- 日K（單月）      https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date=YYYYMMDD&stockNo=2330&response=json
- 全市場當日收盤    https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL
- 本益比/殖利率/淨值比 https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL
- 三大法人買賣超    https://www.twse.com.tw/rwd/zh/fund/T86?date=YYYYMMDD&selectType=ALL&response=json
- 融資融券餘額      https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date=YYYYMMDD&selectType=ALL&response=json
- 即時報價 (MIS)    https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_2330.tw&json=1&delay=0

注意：
- TWSE 對頻繁請求會暫時封鎖 IP，本模組透過 HttpClient 限制每 3 秒 1 次。
- 日K端點一次只回一個月，抓多年資料要逐月呼叫；建議搭配長 TTL 快取。
- 資料欄位為中文字串含千分位，已在此轉成數值。
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from ..schema import standardize_ohlcv
from .base import DataSourceError, get_client, to_float

BASE = "https://www.twse.com.tw/rwd/zh"
OPENAPI = "https://openapi.twse.com.tw/v1"
MIS = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"

_DAY_TTL = 12 * 3600
_HIST_TTL = 30 * 24 * 3600


def _month_range(start: dt.date, end: dt.date) -> list[dt.date]:
    months = []
    cur = dt.date(start.year, start.month, 1)
    while cur <= end:
        months.append(cur)
        cur = dt.date(cur.year + (cur.month // 12), cur.month % 12 + 1, 1)
    return months


def fetch_daily_ohlcv(stock_no: str, start: str | dt.date, end: str | dt.date | None = None) -> pd.DataFrame:
    """抓取上市個股日K（逐月呼叫 STOCK_DAY），回傳標準 OHLCV。volume 為股數，turnover 為成交金額。"""
    start = pd.Timestamp(start).date()
    end = pd.Timestamp(end).date() if end else dt.date.today()
    client = get_client()
    frames = []
    for m in _month_range(start, end):
        is_current = (m.year, m.month) == (dt.date.today().year, dt.date.today().month)
        js = client.get_json(
            f"{BASE}/afterTrading/STOCK_DAY",
            {"date": m.strftime("%Y%m%d"), "stockNo": stock_no, "response": "json"},
            cache_ttl=_DAY_TTL if is_current else _HIST_TTL,
        )
        if js.get("stat") != "OK" or not js.get("data"):
            continue
        # 欄位：日期, 成交股數, 成交金額, 開盤價, 最高價, 最低價, 收盤價, 漲跌價差, 成交筆數
        rows = []
        for r in js["data"]:
            y, mo, d = r[0].split("/")
            rows.append(
                {
                    "date": dt.date(int(y) + 1911, int(mo), int(d)),
                    "open": to_float(r[3]),
                    "high": to_float(r[4]),
                    "low": to_float(r[5]),
                    "close": to_float(r[6]),
                    "volume": to_float(r[1]),
                    "turnover": to_float(r[2]),
                    "transactions": to_float(r[8]),
                }
            )
        frames.append(pd.DataFrame(rows))
    if not frames:
        raise DataSourceError(f"TWSE 無 {stock_no} 資料")
    df = standardize_ohlcv(pd.concat(frames))
    return df.loc[str(start) : str(end)]


def fetch_all_daily_close() -> pd.DataFrame:
    """全市場最近交易日收盤（OpenAPI STOCK_DAY_ALL），供每日掃描用。"""
    js = get_client().get_json(f"{OPENAPI}/exchangeReport/STOCK_DAY_ALL", cache_ttl=3600)
    df = pd.DataFrame(js).rename(
        columns={
            "Code": "code", "Name": "name", "TradeVolume": "volume", "TradeValue": "turnover",
            "OpeningPrice": "open", "HighestPrice": "high", "LowestPrice": "low",
            "ClosingPrice": "close", "Change": "change", "Transaction": "transactions",
        }
    )
    for c in ("volume", "turnover", "open", "high", "low", "close", "change", "transactions"):
        if c in df.columns:
            df[c] = df[c].map(to_float)
    return df.set_index("code")


def fetch_valuation_all() -> pd.DataFrame:
    """全市場本益比 (pe)、殖利率 (dividend_yield %)、股價淨值比 (pb)。"""
    js = get_client().get_json(f"{OPENAPI}/exchangeReport/BWIBBU_ALL", cache_ttl=3600)
    df = pd.DataFrame(js).rename(
        columns={"Code": "code", "Name": "name", "PEratio": "pe", "DividendYield": "dividend_yield", "PBratio": "pb"}
    )
    for c in ("pe", "dividend_yield", "pb"):
        df[c] = df[c].map(to_float)
    return df.set_index("code")[["name", "pe", "dividend_yield", "pb"]]


def fetch_institutional(date: str | dt.date) -> pd.DataFrame:
    """
    三大法人個股買賣超（T86）。回傳以 code 為 index，單位：股。
    欄位：foreign_net, trust_net, dealer_net, total_net
    """
    d = pd.Timestamp(date).strftime("%Y%m%d")
    js = get_client().get_json(
        f"{BASE}/fund/T86", {"date": d, "selectType": "ALL", "response": "json"}, cache_ttl=_HIST_TTL
    )
    if js.get("stat") != "OK":
        raise DataSourceError(f"T86 {d}: {js.get('stat')}")
    fields = js["fields"]
    df = pd.DataFrame(js["data"], columns=fields)
    df = df.rename(columns={fields[0]: "code", fields[1]: "name"})
    df["code"] = df["code"].str.strip()

    def col(name_part: str) -> pd.Series:
        matches = [c for c in df.columns if name_part in c and "買賣超" in c]
        return df[matches[0]].map(to_float) if matches else pd.Series(float("nan"), index=df.index)

    out = pd.DataFrame(
        {
            "name": df["name"].str.strip(),
            "foreign_net": col("外陸資買賣超股數(不含外資自營商)") if any("外陸資" in c for c in df.columns) else col("外資"),
            "trust_net": col("投信"),
            "dealer_net": col("自營商買賣超股數") if any(c == "自營商買賣超股數" for c in df.columns) else col("自營商"),
            "total_net": col("三大法人"),
        }
    )
    out["date"] = pd.Timestamp(date)
    return out.set_index("code")


def fetch_margin(date: str | dt.date) -> pd.DataFrame:
    """
    融資融券餘額（MI_MARGN）。回傳以 code 為 index。
    欄位：margin_balance（融資餘額，張）、short_balance（融券餘額，張）、margin_change、short_change
    """
    d = pd.Timestamp(date).strftime("%Y%m%d")
    js = get_client().get_json(
        f"{BASE}/marginTrading/MI_MARGN", {"date": d, "selectType": "ALL", "response": "json"}, cache_ttl=_HIST_TTL
    )
    if js.get("stat") != "OK":
        raise DataSourceError(f"MI_MARGN {d}: {js.get('stat')}")
    # 個股表在 tables 中最後一張（第一張是市場合計）
    tables = js.get("tables") or [{"fields": js.get("fields"), "data": js.get("data")}]
    tbl = tables[-1]
    df = pd.DataFrame(tbl["data"], columns=tbl["fields"])
    cols = list(df.columns)
    # 官方欄位順序：股票代號, 股票名稱, 融資(買進, 賣出, 現金償還, 前日餘額, 今日餘額, 限額), 融券(...)
    out = pd.DataFrame(
        {
            "name": df[cols[1]].str.strip(),
            "margin_prev": df[cols[5]].map(to_float),
            "margin_balance": df[cols[6]].map(to_float),
            "short_prev": df[cols[11]].map(to_float),
            "short_balance": df[cols[12]].map(to_float),
        }
    )
    out["margin_change"] = out["margin_balance"] - out["margin_prev"]
    out["short_change"] = out["short_balance"] - out["short_prev"]
    out["code"] = df[cols[0]].str.strip()
    out["date"] = pd.Timestamp(date)
    return out.set_index("code")


def fetch_realtime(codes: list[str], market: str = "tse") -> pd.DataFrame:
    """
    即時報價（MIS，約 5 秒延遲）。market='tse' 上市、'otc' 上櫃。
    回傳欄位：name, last, open, high, low, prev_close, volume(張), bid, ask, time
    """
    ex_ch = "|".join(f"{market}_{c}.tw" for c in codes)
    js = get_client().get_json(MIS, {"ex_ch": ex_ch, "json": "1", "delay": "0"})
    rows = []
    for m in js.get("msgArray", []):
        rows.append(
            {
                "code": m.get("c"),
                "name": m.get("n"),
                "last": to_float(m.get("z")),
                "open": to_float(m.get("o")),
                "high": to_float(m.get("h")),
                "low": to_float(m.get("l")),
                "prev_close": to_float(m.get("y")),
                "volume": to_float(m.get("v")),
                "bid": to_float(str(m.get("b", "")).split("_")[0]),
                "ask": to_float(str(m.get("a", "")).split("_")[0]),
                "time": m.get("t"),
            }
        )
    return pd.DataFrame(rows).set_index("code") if rows else pd.DataFrame()
