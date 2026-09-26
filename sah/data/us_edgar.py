"""
SEC EDGAR 官方 XBRL API（免費、無金鑰，但必須設定含 email 的 User-Agent，且 ≤10 req/s）。

- Ticker→CIK 對照：https://www.sec.gov/files/company_tickers.json
- 公司全部財務事實：https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json
- 申報索引（10-K/10-Q/8-K/Form 4 內部人/13F）：https://data.sec.gov/submissions/CIK##########.json

常用 us-gaap 標籤：
  Revenues / RevenueFromContractWithCustomerExcludingAssessedTax, NetIncomeLoss, EarningsPerShareDiluted,
  StockholdersEquity, Assets, Liabilities, NetCashProvidedByUsedInOperatingActivities,
  PaymentsToAcquirePropertyPlantAndEquipment, CommonStockSharesOutstanding (dei: EntityCommonStockSharesOutstanding)
"""
from __future__ import annotations

import pandas as pd

from .base import DataSourceError, get_client

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"

REVENUE_TAGS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"]


def ticker_to_cik(ticker: str) -> int:
    js = get_client().get_json(TICKERS_URL, cache_ttl=7 * 24 * 3600)
    t = ticker.upper()
    for v in js.values():
        if v["ticker"].upper() == t:
            return int(v["cik_str"])
    raise DataSourceError(f"EDGAR 找不到 ticker {ticker}")


def fetch_company_facts(ticker: str) -> dict:
    return get_client().get_json(FACTS_URL.format(cik=ticker_to_cik(ticker)), cache_ttl=24 * 3600)


def facts_to_series(facts: dict, tag: str, taxonomy: str = "us-gaap", unit: str | None = None,
                    forms: tuple[str, ...] = ("10-K", "10-Q")) -> pd.DataFrame:
    """
    取出單一 XBRL 標籤的時間序列。回傳欄位：end, val, fy, fp, form, filed, frame。
    注意：同一期間可能被多份申報重複揭露，已依 (end, fp) 去重保留最新 filed。
    """
    node = facts.get("facts", {}).get(taxonomy, {}).get(tag)
    if not node:
        return pd.DataFrame(columns=["end", "val", "fy", "fp", "form", "filed", "frame"])
    units = node["units"]
    unit = unit or next(iter(units))
    df = pd.DataFrame(units[unit])
    df = df[df["form"].isin(forms)].copy()
    df["end"] = pd.to_datetime(df["end"])
    df["filed"] = pd.to_datetime(df["filed"])
    df = df.sort_values("filed").drop_duplicates(subset=["end", "fp"], keep="last").sort_values("end")
    return df.reset_index(drop=True)


def first_available(facts: dict, tags: list[str], **kw) -> pd.DataFrame:
    for t in tags:
        df = facts_to_series(facts, t, **kw)
        if not df.empty:
            return df
    return pd.DataFrame()


def fetch_fundamentals_summary(ticker: str) -> pd.DataFrame:
    """
    整理年度 (10-K, fp=FY) 基本面表：revenue, net_income, eps_diluted, equity, assets, liabilities,
    operating_cf, capex, shares_out。index 為會計年度結束日。
    """
    facts = fetch_company_facts(ticker)

    def annual(tags, taxonomy="us-gaap"):
        df = first_available(facts, tags if isinstance(tags, list) else [tags], taxonomy=taxonomy, forms=("10-K",))
        if df.empty:
            return pd.Series(dtype=float)
        df = df[df["fp"] == "FY"]
        # 流量科目用 frame 含 'CY####'（整年）者，避免抓到季度值
        if "frame" in df and df["frame"].notna().any():
            fy = df[df["frame"].fillna("").str.fullmatch(r"CY\d{4}")]
            if not fy.empty:
                df = fy
        return df.set_index("end")["val"].astype(float)

    out = pd.DataFrame(
        {
            "revenue": annual(REVENUE_TAGS),
            "net_income": annual("NetIncomeLoss"),
            "eps_diluted": annual("EarningsPerShareDiluted"),
            "equity": annual("StockholdersEquity"),
            "assets": annual("Assets"),
            "liabilities": annual("Liabilities"),
            "operating_cf": annual("NetCashProvidedByUsedInOperatingActivities"),
            "capex": annual("PaymentsToAcquirePropertyPlantAndEquipment"),
            "shares_out": annual("EntityCommonStockSharesOutstanding", taxonomy="dei"),
        }
    )
    out.index.name = "fiscal_year_end"
    return out.sort_index()


def fetch_recent_filings(ticker: str, forms: tuple[str, ...] = ("4", "8-K", "10-Q", "10-K", "13F-HR")) -> pd.DataFrame:
    """最近申報清單（含 Form 4 內部人交易、13F 機構持股）。"""
    js = get_client().get_json(SUBMISSIONS_URL.format(cik=ticker_to_cik(ticker)), cache_ttl=6 * 3600)
    rec = js["filings"]["recent"]
    df = pd.DataFrame({k: rec[k] for k in ("accessionNumber", "filingDate", "form", "primaryDocument")})
    df["filingDate"] = pd.to_datetime(df["filingDate"])
    return df[df["form"].isin(forms)].reset_index(drop=True)
