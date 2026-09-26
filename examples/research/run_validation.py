"""
真實資料驗證：以 examples/research/data/ 的 10 年資料，檢驗 docs/03~06 的策略、籌碼與評分準則。
輸出 Markdown 到 stdout（docs/09_live_validation.md 由此產生）。
    python examples/research/run_validation.py > docs/09_live_validation.md
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from sah.backtest import TW_STOCK, US_STOCK, performance_summary, run_backtest
from sah.chips import institutional_features
from sah.data.local_csv import load_ohlcv_csv
from sah.indicators import kd
from sah.signals import (bollinger_mean_reversion, breakout_signal, kd_signal, ma_cross_signal, macd_signal,
                         regime_filter)
from sah.signals.composite import technical_score
from sah.signals.technical import _to_position, atr_trailing_stop

warnings.filterwarnings("ignore")
DATA = Path(__file__).parent / "data"
PPY = {"TW": 245, "US": 252}


def load_px(prefix: str) -> dict[str, pd.DataFrame]:
    out = {}
    for f in sorted(DATA.glob(f"{prefix}_*_px.csv")):
        df = load_ohlcv_csv(f)
        if "adj_close" in df and df["adj_close"].notna().all():
            k = df["adj_close"] / df["close"]
            for c in ("open", "high", "low", "close"):
                df[c] = df[c] * k
        df = df.dropna()
        if len(df) > 1500:
            out[f.name.split("_")[1]] = df
    return out


# ---------- 策略 ----------
def legacy_kd_signal(df: pd.DataFrame) -> pd.Series:
    """重現原專案：RSV 用 9 日收盤價高低；K<20 黃金交叉買、K>80 死亡交叉賣，無趨勢過濾。"""
    c = df["close"]
    lo, hi = c.rolling(9).min(), c.rolling(9).max()
    rsv = ((c - lo) / (hi - lo).replace(0, np.nan) * 100).fillna(50)
    k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    d = k.ewm(alpha=1 / 3, adjust=False).mean()
    buy = (k > d) & (k.shift(1) <= d.shift(1)) & (k.shift(1) <= 20)
    sell = (k < d) & (k.shift(1) >= d.shift(1)) & (k.shift(1) >= 80)
    return _to_position(buy, sell, df.index)


def regime_switch(df: pd.DataFrame) -> pd.Series:
    reg = regime_filter(df)
    tp, mp = breakout_signal(df, vol_confirm=1.5, adx_min=20), bollinger_mean_reversion(df)
    pos = pd.Series(0, index=df.index)
    m1, m2 = reg["bull"] & reg["trend"], reg["bull"] & ~reg["trend"]
    pos[m1] = tp[m1]
    pos[m2] = mp[m2]
    return atr_trailing_stop(df, pos)


STRATS = {
    "KD 原版（收盤價 RSV、無過濾）": legacy_kd_signal,
    "KD 修正（高低價 RSV、無過濾）": lambda d: kd_signal(d, use_trend_filter=False),
    "KD 修正＋60MA 趨勢過濾": lambda d: kd_signal(d, use_trend_filter=True),
    "MACD（零軸上交叉）": lambda d: macd_signal(d, zero_filter=True),
    "MACD（不過濾零軸）": lambda d: macd_signal(d, zero_filter=False),
    "均線 20/60": lambda d: ma_cross_signal(d, 20, 60),
    "均線 50/200": lambda d: ma_cross_signal(d, 50, 200),
    "突破 55/20＋量比1.5＋ADX20": lambda d: breakout_signal(d, vol_confirm=1.5, adx_min=20),
    "突破 55/20（無量/ADX 過濾）": lambda d: breakout_signal(d, vol_confirm=None, adx_min=None),
    "均線 50/200＋ATR2.5 移動停損": lambda d: atr_trailing_stop(d, ma_cross_signal(d, 50, 200)),
    "布林均值回歸": bollinger_mean_reversion,
    "Regime 切換＋ATR 停損": regime_switch,
    "買進持有": lambda d: pd.Series(1, index=d.index),
}


def eval_strats(px: dict[str, pd.DataFrame], market: str) -> pd.DataFrame:
    cost = TW_STOCK if market == "TW" else US_STOCK
    rows = []
    for name, fn in STRATS.items():
        for code, df in px.items():
            pos = fn(df)
            res = run_backtest(df, pos, cost=cost, lot_size=1)
            s = performance_summary(res.returns, res.equity, res.trades, res.positions, periods_per_year=PPY[market])
            bh = performance_summary(res.benchmark.pct_change().fillna(0), res.benchmark, periods_per_year=PPY[market])
            rows.append({"strategy": name, "code": code, "cagr": s["cagr_pct"], "sharpe": s["sharpe"],
                         "mdd": s["max_drawdown_pct"], "calmar": s["calmar"], "trades": s["n_trades"],
                         "win": s.get("win_rate_pct", np.nan), "pf": s.get("profit_factor", np.nan),
                         "exposure": s.get("exposure_pct", np.nan), "bh_cagr": bh["cagr_pct"], "bh_mdd": bh["max_drawdown_pct"],
                         "beat_bh_calmar": (s["calmar"] > bh["calmar"]) if not np.isnan(s["calmar"]) else False})
    df = pd.DataFrame(rows)
    g = df.groupby("strategy", sort=False)
    out = pd.DataFrame({
        "CAGR中位數%": g["cagr"].median(), "Sharpe中位數": g["sharpe"].median(), "MDD中位數%": g["mdd"].median(),
        "Calmar中位數": g["calmar"].median(), "交易次數中位數": g["trades"].median(), "勝率%": g["win"].median(),
        "盈虧比": df["pf"].replace(np.inf, np.nan).groupby(df["strategy"], sort=False).median(), "曝險%": g["exposure"].median(),
        "Calmar勝過B&H比例%": g["beat_bh_calmar"].mean() * 100, "Sharpe>0比例%": g["sharpe"].apply(lambda x: (x > 0).mean() * 100),
    })
    return out.round(2)


# ---------- 事件研究 ----------
def fwd_ret(close: pd.Series, n: int) -> pd.Series:
    return close.shift(-n) / close - 1


def institutional_study(px: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for code, df in px.items():
        f = DATA / f"tw_{code}_inst.csv"
        if not f.exists():
            continue
        inst = pd.read_csv(f, index_col=0, parse_dates=True)
        inst = inst.reindex(df.index).dropna()
        if len(inst) < 500:
            continue
        feat = institutional_features(inst, df["volume"].reindex(inst.index))
        r5, r20 = fwd_ret(df["close"], 5).reindex(inst.index), fwd_ret(df["close"], 20).reindex(inst.index)
        base5, base20 = r5.mean(), r20.mean()
        conds = {
            "外資連 3 日以上買超": feat["foreign_streak"] >= 3,
            "外資連 3 日以上賣超": feat["foreign_streak"] <= -3,
            "投信連 3 日以上買超": feat["trust_streak"] >= 3,
            "外資 20 日累計買超 > 5% 成交量": feat["foreign_cum_ratio"] > 0.05,
            "外資 20 日累計賣超 > 5% 成交量": feat["foreign_cum_ratio"] < -0.05,
            "inst_score ≥ 2": feat["inst_score"] >= 2,
            "inst_score ≤ -2": feat["inst_score"] <= -2,
        }
        for name, m in conds.items():
            rows.append({"cond": name, "code": code, "n": int(m.sum()), "ex5": (r5[m].mean() - base5) * 100,
                         "ex20": (r20[m].mean() - base20) * 100, "hit20": (r20[m] > 0).mean() * 100})
    df = pd.DataFrame(rows)
    g = df.groupby("cond", sort=False)
    out = pd.DataFrame({"樣本數": g["n"].sum(), "5日超額報酬%(平均)": g["ex5"].mean(), "20日超額報酬%(平均)": g["ex20"].mean(),
                        "20日超額為正的股票比例%": g["ex20"].apply(lambda x: (x > 0).mean() * 100), "20日上漲機率%": g["hit20"].mean()})
    return out.round(2)


def revenue_study(px: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for code, df in px.items():
        f = DATA / f"tw_{code}_rev.csv"
        if not f.exists():
            continue
        rev = pd.read_csv(f, index_col=0, parse_dates=True)
        if len(rev) < 24:
            continue
        # 月營收於次月 10 日前公布 → 以「該月份 +1 月的 11 日之後第一個交易日」為訊號日
        rev["signal_date"] = [df.index[df.index.searchsorted(pd.Timestamp(y, m, 1) + pd.DateOffset(months=1, days=10))]
                              if df.index.searchsorted(pd.Timestamp(y, m, 1) + pd.DateOffset(months=1, days=10)) < len(df) else pd.NaT
                              for y, m in zip(rev["revenue_year"], rev["revenue_month"])]
        rev = rev.dropna(subset=["signal_date"])
        rev["yoy_prev"] = rev["yoy_pct"].shift(1)
        r20 = fwd_ret(df["close"], 20).reindex(rev["signal_date"]).values
        r60 = fwd_ret(df["close"], 60).reindex(rev["signal_date"]).values
        b20, b60 = np.nanmean(r20), np.nanmean(r60)
        conds = {
            "YoY > 20%": rev["yoy_pct"] > 20,
            "YoY > 20% 且較前月加速": (rev["yoy_pct"] > 20) & (rev["yoy_pct"] > rev["yoy_prev"]),
            "YoY < 0": rev["yoy_pct"] < 0,
            "YoY < -20%": rev["yoy_pct"] < -20,
            "創 12 月新高營收": rev["revenue"] >= rev["revenue"].rolling(12).max(),
        }
        for name, m in conds.items():
            m = m.fillna(False).values
            if m.sum() == 0:
                continue
            rows.append({"cond": name, "code": code, "n": int(m.sum()), "ex20": (np.nanmean(r20[m]) - b20) * 100,
                         "ex60": (np.nanmean(r60[m]) - b60) * 100})
    df = pd.DataFrame(rows)
    g = df.groupby("cond", sort=False)
    return pd.DataFrame({"樣本數": g["n"].sum(), "20日超額報酬%": g["ex20"].mean(), "60日超額報酬%": g["ex60"].mean(),
                         "60日超額為正的股票比例%": g["ex60"].apply(lambda x: (x > 0).mean() * 100)}).round(2)


def score_study(px: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for code, df in px.items():
        t = technical_score(df)
        frames.append(pd.DataFrame({"score": t, "r20": fwd_ret(df["close"], 20), "r60": fwd_ret(df["close"], 60)}).dropna())
    all_ = pd.concat(frames)
    bins = pd.cut(all_["score"], [-1, 30, 50, 65, 80, 101], labels=["0-30", "31-50", "51-65", "66-80", "81-100"])
    g = all_.groupby(bins, observed=True)
    return pd.DataFrame({"樣本數": g.size(), "20日平均報酬%": g["r20"].mean() * 100, "60日平均報酬%": g["r60"].mean() * 100,
                         "60日上漲機率%": g["r60"].apply(lambda x: (x > 0).mean() * 100)}).round(2)


def kd_sensitivity(px: dict[str, pd.DataFrame], market: str) -> pd.DataFrame:
    cost = TW_STOCK if market == "TW" else US_STOCK
    rows = []
    for n in (9, 14):
        for os_, ob in ((20, 80), (30, 70)):
            sh = []
            for code, df in px.items():
                pos = kd_signal(df, n=n, oversold=os_, overbought=ob, use_trend_filter=True)
                res = run_backtest(df, pos, cost=cost, lot_size=1)
                sh.append(performance_summary(res.returns, res.equity, None, res.positions, periods_per_year=PPY[market])["sharpe"])
            rows.append({"n": n, "超賣/超買": f"{os_}/{ob}", "Sharpe中位數": np.nanmedian(sh), "Sharpe>0比例%": np.mean(np.array(sh) > 0) * 100})
    return pd.DataFrame(rows).round(2)


def md(df: pd.DataFrame, index_name: str = "") -> str:
    df = df.copy()
    df.index.name = index_name
    return df.reset_index().to_markdown(index=False)


def main() -> None:
    tw, us = load_px("tw"), load_px("us")
    tw_stocks = {k: v for k, v in tw.items() if k != "0050"}
    us_stocks = {k: v for k, v in us.items() if k != "SPY"}
    span = lambda d: f"{min(x.index[0] for x in d.values()).date()} ～ {max(x.index[-1] for x in d.values()).date()}"
    print("# 09 真實資料驗證報告（自動產生）\n")
    print(f"> 產生方式：`python examples/research/run_validation.py`。資料：台股 {len(tw_stocks)} 檔（Yahoo 還原價，{span(tw_stocks)}）、"
          f"美股 {len(us_stocks)} 檔（Yahoo 還原價，{span(us_stocks)}）。回測皆扣成本（TW_STOCK／US_STOCK）、t+1 開盤成交、lot_size=1。\n")
    print("> ⚠️ 樣本為目前的大型權值股（存活者偏差、且 2015–2026 為台美股大多頭），**絕對報酬數字偏樂觀**；請只看策略之間的相對比較與方向。\n")
    print("## 1. 策略橫向比較（每檔各跑一次，取中位數）\n")
    print("### 1.1 台股\n"); print(md(eval_strats(tw_stocks, "TW"), "策略")); print()
    print("### 1.2 美股\n"); print(md(eval_strats(us_stocks, "US"), "策略")); print()
    print("## 2. KD 參數敏感度（含 60MA 趨勢過濾）\n")
    print("### 台股\n"); print(kd_sensitivity(tw_stocks, "TW").to_markdown(index=False)); print()
    print("### 美股\n"); print(kd_sensitivity(us_stocks, "US").to_markdown(index=False)); print()
    print("## 3. 台股籌碼事件研究（訊號日收盤 → 未來 5／20 日，相對該股無條件平均的超額報酬）\n")
    print(md(institutional_study(tw_stocks), "條件")); print()
    print("## 4. 台股月營收事件研究（公布後首個交易日 → 未來 20／60 日超額報酬）\n")
    print(md(revenue_study(tw_stocks), "條件")); print()
    print("## 5. 技術分數分桶 vs 未來報酬\n")
    print("### 台股\n"); print(md(score_study(tw_stocks), "technical_score")); print()
    print("### 美股\n"); print(md(score_study(us_stocks), "technical_score")); print()


if __name__ == "__main__":
    main()
