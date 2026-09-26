"""
基本面指標計算。皆為純函式，輸入 float 或 Series，回傳同型別。
研究依據見 docs/04_fundamental_analysis_guidelines.md。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def pe_ratio(price, eps_ttm):
    """本益比。eps_ttm ≤ 0 時回 NaN（虧損公司本益比無意義）。"""
    eps = pd.Series(eps_ttm) if not np.isscalar(eps_ttm) else eps_ttm
    if np.isscalar(eps):
        return price / eps if eps and eps > 0 else np.nan
    return (price / eps).where(eps > 0)


def peg_ratio(pe, eps_growth_pct):
    """PEG = PE / 年成長率(%)。<1 便宜、>2 偏貴（Lynch）。"""
    if np.isscalar(eps_growth_pct):
        return pe / eps_growth_pct if eps_growth_pct and eps_growth_pct > 0 else np.nan
    g = pd.Series(eps_growth_pct)
    return (pe / g).where(g > 0)


def roe(net_income, equity):
    """股東權益報酬率。台股長期 ROE > 15% 為優質；美股常用 > 15~20%。"""
    return net_income / equity


def dividend_yield(dps, price):
    """現金殖利率 (%)。台股高股息族群常以 > 4% 為門檻，但需搭配盈餘配發率 < 100% 檢查可持續性。"""
    return dps / price * 100


def fcf_yield(operating_cf, capex, market_cap):
    """自由現金流收益率 = (營業現金流 - 資本支出) / 市值。"""
    return (operating_cf - np.abs(capex)) / market_cap


def graham_number(eps, book_value_per_share):
    """葛拉漢數 = sqrt(22.5 × EPS × BVPS)，粗略內在價值上限。"""
    prod = 22.5 * eps * book_value_per_share
    if np.isscalar(prod):
        return np.sqrt(prod) if prod > 0 else np.nan
    return np.sqrt(pd.Series(prod).clip(lower=0)).where(pd.Series(prod) > 0)


def net_debt_to_equity(total_debt, cash, equity):
    return (total_debt - cash) / equity


def revenue_growth_yoy(revenue: pd.Series, periods: int = 4) -> pd.Series:
    """季營收 YoY（periods=4）；月營收請用 periods=12。"""
    return revenue.pct_change(periods) * 100


def cagr(start_value: float, end_value: float, years: float) -> float:
    if start_value <= 0 or years <= 0:
        return np.nan
    return (end_value / start_value) ** (1 / years) - 1


def piotroski_f_score(cur: dict, prev: dict) -> int:
    """
    Piotroski (2000) F-Score，0~9 分，≥7 為財務體質強。cur/prev 為本年度與前一年度財報 dict，鍵：
      net_income, operating_cf, assets, long_term_debt, current_assets, current_liabilities,
      shares_out, gross_profit, revenue
    """
    s = 0
    roa_c = cur["net_income"] / cur["assets"]
    roa_p = prev["net_income"] / prev["assets"]
    s += roa_c > 0                                        # 1 獲利
    s += cur["operating_cf"] > 0                          # 2 營業現金流為正
    s += roa_c > roa_p                                    # 3 ROA 改善
    s += cur["operating_cf"] / cur["assets"] > roa_c      # 4 現金流 > 盈餘（品質）
    s += cur["long_term_debt"] / cur["assets"] < prev["long_term_debt"] / prev["assets"]  # 5 槓桿下降
    cr_c = cur["current_assets"] / cur["current_liabilities"]
    cr_p = prev["current_assets"] / prev["current_liabilities"]
    s += cr_c > cr_p                                      # 6 流動比率改善
    s += cur["shares_out"] <= prev["shares_out"]          # 7 無增資稀釋
    gm_c = cur["gross_profit"] / cur["revenue"]
    gm_p = prev["gross_profit"] / prev["revenue"]
    s += gm_c > gm_p                                      # 8 毛利率改善
    s += cur["revenue"] / cur["assets"] > prev["revenue"] / prev["assets"]  # 9 資產週轉率改善
    return int(s)
