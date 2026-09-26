"""
公開資訊觀測站 (MOPS) 基本面資料。免費、無需金鑰，但頻率限制嚴格（本模組每 5 秒 1 次）。

- 月營收彙總表（全上市/上櫃）— 2024 年 MOPS 改版後舊版頁面移至 mopsov 網域：
  https://mopsov.twse.com.tw/nas/t21/{sii|otc}/t21sc03_{民國年}_{月}_0.html （實測 2026/09 可用；mops.twse.com.tw 同路徑回 404）
  例：2025 年 8 月上市 → t21sc03_114_8_0.html
- 個別公司財報請優先使用 tw_finmind（TaiwanStockFinancialStatements、TaiwanStockBalanceSheet），
  MOPS 的財報頁面為 POST 表單且結構常變，不建議直接爬。
"""
from __future__ import annotations

import io

import pandas as pd

from .base import DataSourceError, get_client

MOPS_NAS = "https://mopsov.twse.com.tw/nas/t21"


def fetch_monthly_revenue(year: int, month: int, board: str = "sii") -> pd.DataFrame:
    """
    全市場月營收。board='sii' 上市、'otc' 上櫃。年份為西元。
    回傳欄位：code, name, revenue（當月營收，千元）, revenue_last_month, revenue_last_year,
              mom_pct, yoy_pct, cum_revenue, cum_last_year, cum_yoy_pct
    """
    roc_year = year - 1911
    url = f"{MOPS_NAS}/{board}/t21sc03_{roc_year}_{month}_0.html"
    resp = get_client().get(url, cache_ttl=30 * 24 * 3600)  # HttpClient 對 twse 網域自動用瀏覽器 UA
    resp.encoding = "big5"  # MOPS 舊頁為 big5
    try:
        tables = pd.read_html(io.StringIO(resp.text), flavor="lxml")
    except ValueError as exc:
        raise DataSourceError(f"MOPS 月營收頁解析失敗: {url}") from exc
    frames = []
    for t in tables:
        if t.shape[1] < 10:
            continue
        cols = ["code", "name", "revenue", "revenue_last_month", "revenue_last_year", "mom_pct", "yoy_pct",
                "cum_revenue", "cum_last_year", "cum_yoy_pct"]
        t = t.iloc[:, :10]
        t.columns = cols
        t = t[t["code"].astype(str).str.fullmatch(r"\d{4,6}")]
        frames.append(t)
    if not frames:
        raise DataSourceError(f"MOPS 月營收無有效表格: {url}")
    df = pd.concat(frames, ignore_index=True)
    for c in df.columns[2:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["year"], df["month"] = year, month
    return df.set_index("code")
