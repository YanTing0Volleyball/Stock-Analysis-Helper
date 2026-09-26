"""
FinMind 台股整合 API（https://finmindtrade.com）。
- 免費：未登入約 300 次/小時，註冊取得 token 後 600 次/小時；付費方案再提高（CP 值高，適合個人）。
- 涵蓋：日K、還原權息、三大法人、融資融券、借券、月營收、財報、股利、董監持股等。
- 為 TWSE/TPEx/MOPS 直連的備援與統一入口，欄位乾淨、上市上櫃同一介面。

主要 dataset：
  TaiwanStockPrice, TaiwanStockPriceAdj, TaiwanStockInstitutionalInvestorsBuySell,
  TaiwanStockMarginPurchaseShortSale, TaiwanStockMonthRevenue, TaiwanStockFinancialStatements,
  TaiwanStockBalanceSheet, TaiwanStockDividend, TaiwanStockPER, TaiwanStockShareholding,
  TaiwanStockSecuritiesLending, TaiwanStockNews
"""
from __future__ import annotations

import pandas as pd

from ..config import settings
from ..schema import standardize_ohlcv
from .base import DataSourceError, get_client

API = "https://api.finmindtrade.com/api/v4/data"


def fetch_dataset(dataset: str, data_id: str | None = None, start: str | None = None, end: str | None = None,
                  token: str | None = None, cache_ttl: float = 12 * 3600) -> pd.DataFrame:
    params = {"dataset": dataset}
    if data_id:
        params["data_id"] = data_id
    if start:
        params["start_date"] = start
    if end:
        params["end_date"] = end
    tok = token or settings.finmind_token
    if tok:
        params["token"] = tok
    js = get_client().get_json(API, params, cache_ttl=cache_ttl)
    if js.get("status") != 200:
        raise DataSourceError(f"FinMind {dataset}: {js.get('msg')}")
    return pd.DataFrame(js.get("data", []))


def fetch_daily_ohlcv(stock_id: str, start: str, end: str | None = None, adjusted: bool = False) -> pd.DataFrame:
    """日K（上市＋上櫃通用）。adjusted=True 取還原權息價（適合長期回測）。"""
    ds = "TaiwanStockPriceAdj" if adjusted else "TaiwanStockPrice"
    df = fetch_dataset(ds, stock_id, start, end)
    if df.empty:
        raise DataSourceError(f"FinMind 無 {stock_id} 價格資料")
    df = df.rename(columns={"max": "high", "min": "low", "Trading_Volume": "volume", "Trading_money": "turnover"})
    return standardize_ohlcv(df[["date", "open", "high", "low", "close", "volume", "turnover"]])


def fetch_institutional(stock_id: str, start: str, end: str | None = None) -> pd.DataFrame:
    """個股三大法人買賣超時間序列，欄位：foreign_net, trust_net, dealer_net, total_net（股）。"""
    df = fetch_dataset("TaiwanStockInstitutionalInvestorsBuySell", stock_id, start, end)
    if df.empty:
        return pd.DataFrame(columns=["foreign_net", "trust_net", "dealer_net", "total_net"])
    df["net"] = df["buy"] - df["sell"]
    p = df.pivot_table(index="date", columns="name", values="net", aggfunc="sum").fillna(0)
    p.index = pd.to_datetime(p.index)

    def g(*names: str) -> pd.Series:
        s = pd.Series(0.0, index=p.index)
        for n in names:
            if n in p.columns:
                s = s + p[n]
        return s

    out = pd.DataFrame(index=p.index)
    out["foreign_net"] = g("Foreign_Investor", "Foreign_Dealer_Self")
    out["trust_net"] = g("Investment_Trust")
    out["dealer_net"] = g("Dealer_self", "Dealer_Hedging")
    out["total_net"] = out[["foreign_net", "trust_net", "dealer_net"]].sum(axis=1)
    out.index.name = "date"
    return out


def fetch_margin(stock_id: str, start: str, end: str | None = None) -> pd.DataFrame:
    df = fetch_dataset("TaiwanStockMarginPurchaseShortSale", stock_id, start, end)
    if df.empty:
        return pd.DataFrame()
    out = pd.DataFrame(
        {
            "margin_balance": df["MarginPurchaseTodayBalance"],
            "short_balance": df["ShortSaleTodayBalance"],
        },
        index=pd.to_datetime(df["date"]),
    )
    out["margin_change"] = out["margin_balance"].diff()
    out["short_change"] = out["short_balance"].diff()
    out.index.name = "date"
    return out


def fetch_monthly_revenue(stock_id: str, start: str, end: str | None = None) -> pd.DataFrame:
    df = fetch_dataset("TaiwanStockMonthRevenue", stock_id, start, end, cache_ttl=7 * 24 * 3600)
    if df.empty:
        return pd.DataFrame()
    out = df[["date", "revenue", "revenue_year", "revenue_month"]].copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.set_index("date").sort_index()
    out["yoy_pct"] = out["revenue"].pct_change(12) * 100
    out["mom_pct"] = out["revenue"].pct_change(1) * 100
    return out


def fetch_financial_statements(stock_id: str, start: str, end: str | None = None) -> pd.DataFrame:
    """
    綜合損益表（季），轉成寬表：index=季底日期，columns=會計科目（Revenue, GrossProfit,
    OperatingIncome, IncomeAfterTaxes, EPS ...）。
    """
    df = fetch_dataset("TaiwanStockFinancialStatements", stock_id, start, end, cache_ttl=7 * 24 * 3600)
    if df.empty:
        return pd.DataFrame()
    wide = df.pivot_table(index="date", columns="type", values="value", aggfunc="first")
    wide.index = pd.to_datetime(wide.index)
    return wide.sort_index()


def fetch_balance_sheet(stock_id: str, start: str, end: str | None = None) -> pd.DataFrame:
    df = fetch_dataset("TaiwanStockBalanceSheet", stock_id, start, end, cache_ttl=7 * 24 * 3600)
    if df.empty:
        return pd.DataFrame()
    wide = df.pivot_table(index="date", columns="type", values="value", aggfunc="first")
    wide.index = pd.to_datetime(wide.index)
    return wide.sort_index()
