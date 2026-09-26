"""
美股資金流向／持股結構。
資料來源：
- 內部人交易 Form 4：SEC EDGAR（sah.data.us_edgar.fetch_recent_filings 取索引，明細需解析 XML；
  或用免費彙整站 openinsider.com 匯出 CSV）。
- 機構持股 13F：EDGAR（季度、延遲 45 天，僅適合長線參考）。
- 空單餘額：FINRA 每半月公布（https://www.finra.org/finra-data/browse-catalog/equity-short-interest/data），
  或 Yahoo quoteSummary defaultKeyStatistics 的 shortPercentOfFloat。
- 期權 Put/Call：CBOE 每日免費 CSV。

準則摘要（詳見 docs/05）：
- 內部人「公開市場買進」（非行權）叢集 ≥ 3 人／季 → 中期偏多；賣出訊號雜訊高（多為稠現／稅務）。
- 空單佔流通比 > 20% 且 days-to-cover > 5 → 高波動、軋空風險，短線勿放空、長線需評估基本面是否惡化。
"""
from __future__ import annotations

import pandas as pd


def insider_features(trades: pd.DataFrame, lookback_days: int = 90) -> dict:
    """
    trades 欄位：date, insider（姓名）, type（'P' 公開市場買、'S' 賣、其他忽略）, value（美元）。
    回傳最近 lookback_days 的：buyers（買進人數）、buy_value、sell_value、net_value、cluster_buy（bool）。
    """
    if trades.empty:
        return {"buyers": 0, "buy_value": 0.0, "sell_value": 0.0, "net_value": 0.0, "cluster_buy": False}
    t = trades.copy()
    t["date"] = pd.to_datetime(t["date"])
    recent = t[t["date"] >= t["date"].max() - pd.Timedelta(days=lookback_days)]
    buys = recent[recent["type"] == "P"]
    sells = recent[recent["type"] == "S"]
    buy_value = float(buys["value"].sum())
    sell_value = float(sells["value"].sum())
    return {
        "buyers": int(buys["insider"].nunique()),
        "buy_value": buy_value,
        "sell_value": sell_value,
        "net_value": buy_value - sell_value,
        "cluster_buy": bool(buys["insider"].nunique() >= 3),
    }


def short_interest_features(short_shares: float, float_shares: float, avg_daily_volume: float) -> dict:
    """回傳 short_pct_float (%)、days_to_cover、squeeze_risk（bool）。"""
    pct = short_shares / float_shares * 100 if float_shares else float("nan")
    dtc = short_shares / avg_daily_volume if avg_daily_volume else float("nan")
    return {"short_pct_float": pct, "days_to_cover": dtc, "squeeze_risk": bool(pct > 20 and dtc > 5)}
