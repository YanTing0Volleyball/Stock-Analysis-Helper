"""
單一公司分析數據表：把技術、趨勢、月營收、法人、估值、歷史策略績效整理成一列 dict。
APP 每日對全市場跑一次 analyze_company()，即得到「個股分析數據」。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..backtest import TW_STOCK, US_STOCK, performance_summary, run_backtest
from ..chips import institutional_features
from ..fundamentals import revenue_momentum
from ..indicators import atr, kd, macd, rsi, sma
from ..signals import kd_state, ma_cross_signal, momentum_12_1
from ..signals.composite import (CompositeWeights, chips_score, composite_score, fundamental_score, score_to_action,
                                 technical_score)

COMPANY_COLUMNS = [
    "code", "name", "market", "industry", "date", "close", "ret_1m_pct", "ret_3m_pct", "ret_12m_pct",
    "sma50", "sma200", "trend_bull", "dist_sma200_pct", "high_52w_pct", "rsi14", "kd_k", "kd_d", "kd_state",
    "macd_hist", "atr14_pct", "vol_20d_annual_pct", "avg_turnover_20d", "momentum_12_1_pct",
    "technical_score", "revenue_yoy_pct", "revenue_yoy_prev_pct", "revenue_signal", "revenue_new_12m_high",
    "foreign_cum20_ratio", "inst_score", "pe", "pb", "dividend_yield", "fundamental_score", "chips_score",
    "composite_score", "action", "stop_loss", "bh_cagr_pct", "bh_mdd_pct", "ma50_200_cagr_pct", "ma50_200_sharpe",
    "ma50_200_mdd_pct", "ma50_200_calmar_vs_bh", "years_of_data",
]


def analyze_company(df: pd.DataFrame, *, code: str, name: str = "", market: str = "TW", industry: str = "",
                    monthly_revenue: pd.Series | None = None, inst: pd.DataFrame | None = None,
                    valuation: dict | None = None, weights: CompositeWeights | None = None) -> dict:
    """
    df：標準 OHLCV（建議還原價）。monthly_revenue：月營收 Series（index 為月份）。inst：法人時間序列。
    valuation：{"pe":..,"pb":..,"dividend_yield":..}。回傳 COMPANY_COLUMNS 對應的 dict。
    """
    c = df["close"]
    last = df.index[-1]
    out: dict = {"code": code, "name": name, "market": market, "industry": industry, "date": str(last.date()),
                 "close": float(c.iloc[-1]), "years_of_data": round(len(df) / (245 if market == "TW" else 252), 1)}
    for k, n in (("ret_1m_pct", 21), ("ret_3m_pct", 63), ("ret_12m_pct", 252)):
        out[k] = float((c.iloc[-1] / c.iloc[-n - 1] - 1) * 100) if len(c) > n else np.nan
    s50, s200 = sma(c, 50), sma(c, 200)
    out["sma50"], out["sma200"] = _last(s50), _last(s200)
    out["trend_bull"] = bool(c.iloc[-1] > _last(s200) and _last(s50) > _last(s200)) if not np.isnan(_last(s200)) else None
    out["dist_sma200_pct"] = float((c.iloc[-1] / _last(s200) - 1) * 100) if not np.isnan(_last(s200)) else np.nan
    out["high_52w_pct"] = float((c.iloc[-1] / c.iloc[-252:].max() - 1) * 100)
    out["rsi14"] = _last(rsi(c, 14))
    k = kd(df)
    out["kd_k"], out["kd_d"] = _last(k["k"]), _last(k["d"])
    out["kd_state"] = kd_state(k["k"], k["d"]).iloc[-1]
    out["macd_hist"] = _last(macd(c)["hist"])
    a = _last(atr(df))
    out["atr14_pct"] = float(a / c.iloc[-1] * 100) if not np.isnan(a) else np.nan
    out["vol_20d_annual_pct"] = float(np.log(c / c.shift(1)).tail(20).std() * np.sqrt(252) * 100)
    out["avg_turnover_20d"] = float((c * df["volume"]).tail(20).mean())
    out["momentum_12_1_pct"] = _last(momentum_12_1(c)) * 100 if len(c) > 252 else np.nan
    tech = technical_score(df)
    out["technical_score"] = _last(tech)

    fund_in: dict = dict(valuation or {})
    out["revenue_yoy_pct"] = out["revenue_yoy_prev_pct"] = np.nan
    out["revenue_signal"], out["revenue_new_12m_high"] = None, None
    if monthly_revenue is not None and len(monthly_revenue.dropna()) >= 13:
        rm = revenue_momentum(monthly_revenue.dropna())
        out["revenue_yoy_pct"] = _last(rm["yoy_pct"])
        out["revenue_yoy_prev_pct"] = _last(rm["yoy_prev"])
        out["revenue_signal"] = int(rm["signal"].iloc[-1])
        out["revenue_new_12m_high"] = bool(rm["new_12m_high"].iloc[-1])
        fund_in["revenue_yoy"], fund_in["revenue_yoy_prev"] = out["revenue_yoy_pct"], out["revenue_yoy_prev_pct"]
    out["pe"], out["pb"], out["dividend_yield"] = (fund_in.get(x, np.nan) for x in ("pe", "pb", "dividend_yield"))
    fund = fundamental_score(fund_in) if fund_in else None
    out["fundamental_score"] = fund if fund is not None else np.nan

    out["foreign_cum20_ratio"], out["inst_score"], chips = np.nan, np.nan, None
    if inst is not None and len(inst) > 20:
        feat = institutional_features(inst, df["volume"])
        out["foreign_cum20_ratio"] = _last(feat.get("foreign_cum_ratio", pd.Series(dtype=float)))
        out["inst_score"] = int(feat["inst_score"].iloc[-1])
        chips = float(chips_score(feat["inst_score"]).iloc[-1])
    out["chips_score"] = chips if chips is not None else np.nan

    w = weights or (CompositeWeights() if market == "TW" else CompositeWeights.us_large_cap())
    comp = composite_score(technical=out["technical_score"], fundamental=fund, chips=chips, weights=w)
    out["composite_score"] = float(comp)
    out["action"] = score_to_action(float(comp), in_position=bool(out["trend_bull"]))
    out["stop_loss"] = float(c.iloc[-1] - 2 * a) if not np.isnan(a) else np.nan

    # 歷史策略績效（供 APP 顯示「此股適不適合趨勢策略」）
    cost = TW_STOCK if market == "TW" else US_STOCK
    ppy = 245 if market == "TW" else 252
    res = run_backtest(df, ma_cross_signal(df, 50, 200), cost=cost, lot_size=1)
    st = performance_summary(res.returns, res.equity, res.trades, res.positions, periods_per_year=ppy)
    bh = performance_summary(res.benchmark.pct_change().fillna(0), res.benchmark, periods_per_year=ppy)
    out.update({"bh_cagr_pct": bh["cagr_pct"], "bh_mdd_pct": bh["max_drawdown_pct"], "ma50_200_cagr_pct": st["cagr_pct"],
                "ma50_200_sharpe": st["sharpe"], "ma50_200_mdd_pct": st["max_drawdown_pct"],
                "ma50_200_calmar_vs_bh": bool(st["calmar"] > bh["calmar"]) if not (np.isnan(st["calmar"]) or np.isnan(bh["calmar"])) else None})
    return {k: out.get(k) for k in COMPANY_COLUMNS}


def _last(s: pd.Series) -> float:
    return float(s.iloc[-1]) if len(s) and not pd.isna(s.iloc[-1]) else np.nan
