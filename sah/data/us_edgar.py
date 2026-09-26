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


def merged_series(facts: dict, tags: list[str], **kw) -> pd.DataFrame:
    """
    合併多個同義標籤（公司會隨年代改用不同標籤，如 Apple 營收 2018 前 SalesRevenueNet、之後
    RevenueFromContractWithCustomerExcludingAssessedTax），依 end 去重、保留最新 filed。
    """
    frames = [facts_to_series(facts, t, **kw) for t in tags]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=["end", "val", "fy", "fp", "form", "filed", "frame"])
    df = pd.concat(frames).sort_values("filed").drop_duplicates(subset=["end", "fp"], keep="last")
    return df.sort_values("end").reset_index(drop=True)


first_available = merged_series  # 向後相容


def fetch_fundamentals_summary(ticker: str) -> pd.DataFrame:
    """
    整理年度 (10-K, fp=FY) 基本面表：revenue, net_income, eps_diluted, equity, assets, liabilities,
    operating_cf, capex, shares_out。index 為會計年度（以期末日的西元年表示，例如 Apple FY2025 期末 2025-09-27 → 2025），
    另附 fiscal_year_end 欄。
    """
    facts = fetch_company_facts(ticker)

    def annual(tags, taxonomy="us-gaap", flow=True):
        df = merged_series(facts, tags if isinstance(tags, list) else [tags], taxonomy=taxonomy, forms=("10-K",))
        if df.empty:
            return pd.Series(dtype=float)
        df = df[df["fp"] == "FY"]
        if flow and "frame" in df and df["frame"].notna().any():
            # 流量科目只取整年 frame (CY####)，避免 10-K 內揭露的季度值
            fy = df[df["frame"].fillna("").str.fullmatch(r"CY\d{4}")]
            if not fy.empty:
                df = fy
        df = df.assign(year=df["end"].dt.year).drop_duplicates("year", keep="last")
        return df.set_index("year")["val"].astype(float)

    out = pd.DataFrame(
        {
            "revenue": annual(REVENUE_TAGS),
            "net_income": annual("NetIncomeLoss"),
            "eps_diluted": annual("EarningsPerShareDiluted"),
            "equity": annual("StockholdersEquity", flow=False),
            "assets": annual("Assets", flow=False),
            "liabilities": annual("Liabilities", flow=False),
            "operating_cf": annual("NetCashProvidedByUsedInOperatingActivities"),
            "capex": annual("PaymentsToAcquirePropertyPlantAndEquipment"),
            "shares_out": annual("EntityCommonStockSharesOutstanding", taxonomy="dei", flow=False),
        }
    )
    ends = merged_series(facts, ["NetIncomeLoss"], forms=("10-K",))
    ends = ends[ends["fp"] == "FY"].assign(year=lambda d: d["end"].dt.year).drop_duplicates("year", keep="last")
    out["fiscal_year_end"] = ends.set_index("year")["end"]
    out.index.name = "fiscal_year"
    return out.sort_index()


def fetch_recent_filings(ticker: str, forms: tuple[str, ...] = ("4", "8-K", "10-Q", "10-K", "13F-HR")) -> pd.DataFrame:
    """最近申報清單（含 Form 4 內部人交易、13F 機構持股）。"""
    js = get_client().get_json(SUBMISSIONS_URL.format(cik=ticker_to_cik(ticker)), cache_ttl=6 * 3600)
    rec = js["filings"]["recent"]
    df = pd.DataFrame({k: rec[k] for k in ("accessionNumber", "filingDate", "form", "primaryDocument")})
    df["filingDate"] = pd.to_datetime(df["filingDate"])
    return df[df["form"].isin(forms)].reset_index(drop=True)
