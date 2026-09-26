"""
全市場驗證＋每家公司分析數據。
    python examples/research/run_universe_validation.py tw|us
輸出：
- stdout：Markdown 統計（策略比較、技術分數分桶、月營收事件研究、流動性分層）
- analysis/{tw,us}_companies.csv：每家公司一列（sah.analysis.analyze_company）
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from sah.analysis import analyze_company
from sah.backtest import TW_STOCK, US_STOCK, performance_summary, run_backtest
from sah.data.local_csv import load_ohlcv_csv
from sah.signals import bollinger_mean_reversion, breakout_signal, kd_signal, ma_cross_signal, macd_signal
from sah.signals.composite import technical_score

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent / "data" / "universe"
OUT = Path(__file__).parents[2] / "analysis"
PPY = {"tw": 245, "us": 252}
STRATS = {
    "均線 50/200": lambda d: ma_cross_signal(d, 50, 200),
    "均線 20/60": lambda d: ma_cross_signal(d, 20, 60),
    "KD 9/20/80＋60MA": lambda d: kd_signal(d, use_trend_filter=True),
    "KD 9/20/80 無過濾": lambda d: kd_signal(d, use_trend_filter=False),
    "MACD 12/26/9": lambda d: macd_signal(d),
    "突破 55/20": lambda d: breakout_signal(d),
    "布林均值回歸": bollinger_mean_reversion,
    "買進持有": lambda d: pd.Series(1, index=d.index),
}


def load_all(market: str) -> dict[str, pd.DataFrame]:
    out = {}
    for f in sorted((ROOT / f"px_{market}").glob("*.csv")):
        df = load_ohlcv_csv(f)
        if "adj_close" in df:
            k = df["adj_close"] / df["close"]
            for c in ("open", "high", "low", "close"):
                df[c] = df[c] * k
        df = df.dropna()
        if len(df) >= 500 and (df["close"] > 0).all():
            out[f.stem] = df
    return out


def load_revenue_tw() -> dict[str, pd.Series]:
    """合併 MOPS 逐月全市場檔 → {code: 月營收 Series}；若無 MOPS 檔則用 FinMind 逐檔檔案。"""
    d = ROOT / "revenue"
    frames = []
    for f in sorted(d.glob("*.csv")) if d.exists() else []:
        t = pd.read_csv(f, dtype={"code": str})
        if {"code", "revenue", "year", "month"} <= set(t.columns):
            frames.append(t[["code", "revenue", "year", "month"]])
    out: dict[str, pd.Series] = {}
    if frames:
        allr = pd.concat(frames)
        allr["date"] = pd.to_datetime(dict(year=allr["year"], month=allr["month"], day=1))
        for code, g in allr.groupby("code"):
            out[code] = g.set_index("date")["revenue"].sort_index()
    d2 = ROOT / "revenue_finmind"
    for f in sorted(d2.glob("*.csv")) if d2.exists() else []:
        t = pd.read_csv(f, index_col=0, parse_dates=True)
        if "revenue" in t and f.stem not in out:
            s = t["revenue"].copy()
            s.index = pd.to_datetime(dict(year=t["revenue_year"], month=t["revenue_month"], day=1))
            out[f.stem] = s.sort_index()
    return out


def load_inst_tw() -> dict[str, pd.DataFrame]:
    d = ROOT / "inst"
    return {f.stem: pd.read_csv(f, index_col=0, parse_dates=True) for f in sorted(d.glob("*.csv"))} if d.exists() else {}


def strat_table(px: dict[str, pd.DataFrame], market: str) -> pd.DataFrame:
    cost = TW_STOCK if market == "tw" else US_STOCK
    rows = []
    for name, fn in STRATS.items():
        for code, df in px.items():
            res = run_backtest(df, fn(df), cost=cost, lot_size=1)
            s = performance_summary(res.returns, res.equity, res.trades, res.positions, periods_per_year=PPY[market])
            bh = performance_summary(res.benchmark.pct_change().fillna(0), res.benchmark, periods_per_year=PPY[market])
            rows.append({"strategy": name, "code": code, "cagr": s["cagr_pct"], "sharpe": s["sharpe"], "mdd": s["max_drawdown_pct"],
                         "calmar": s["calmar"], "trades": s["n_trades"], "pf": s.get("profit_factor", np.nan),
                         "beat": (s["calmar"] > bh["calmar"]) if not (np.isnan(s["calmar"]) or np.isnan(bh["calmar"])) else False,
                         "beat_cagr": s["cagr_pct"] > bh["cagr_pct"]})
    df = pd.DataFrame(rows)
    g = df.groupby("strategy", sort=False)
    return pd.DataFrame({"檔數": g.size(), "CAGR中位數%": g["cagr"].median(), "Sharpe中位數": g["sharpe"].median(),
                         "MDD中位數%": g["mdd"].median(), "Calmar中位數": g["calmar"].median(), "交易次數中位數": g["trades"].median(),
                         "盈虧比中位數": df["pf"].replace(np.inf, np.nan).groupby(df["strategy"], sort=False).median(),
                         "Calmar勝B&H%": g["beat"].mean() * 100, "CAGR勝B&H%": g["beat_cagr"].mean() * 100,
                         "Sharpe>0%": g["sharpe"].apply(lambda x: (x > 0).mean() * 100)}).round(2)


def liquidity_buckets(px: dict[str, pd.DataFrame], market: str) -> pd.DataFrame:
    """依平均成交金額分四層，看 50/200 與 B&H 的差異是否隨流動性變化。"""
    cost = TW_STOCK if market == "tw" else US_STOCK
    rows = []
    for code, df in px.items():
        liq = float((df["close"] * df["volume"]).tail(250).mean())
        res = run_backtest(df, ma_cross_signal(df, 50, 200), cost=cost, lot_size=1)
        s = performance_summary(res.returns, res.equity, None, res.positions, periods_per_year=PPY[market])
        bh = performance_summary(res.benchmark.pct_change().fillna(0), res.benchmark, periods_per_year=PPY[market])
        rows.append({"code": code, "liq": liq, "sharpe": s["sharpe"], "mdd": s["max_drawdown_pct"], "bh_sharpe": bh["sharpe"],
                     "bh_mdd": bh["max_drawdown_pct"], "bh_cagr": bh["cagr_pct"]})
    df = pd.DataFrame(rows)
    df["層"] = pd.qcut(df["liq"], 4, labels=["Q1 最低流動性", "Q2", "Q3", "Q4 最高流動性"])
    g = df.groupby("層", observed=True)
    return pd.DataFrame({"檔數": g.size(), "B&H CAGR中位數%": g["bh_cagr"].median(), "B&H Sharpe": g["bh_sharpe"].median(),
                         "B&H MDD%": g["bh_mdd"].median(), "50/200 Sharpe": g["sharpe"].median(), "50/200 MDD%": g["mdd"].median()}).round(2)


def score_buckets(px: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for df in px.values():
        t = technical_score(df)
        frames.append(pd.DataFrame({"score": t, "r20": df["close"].shift(-20) / df["close"] - 1,
                                    "r60": df["close"].shift(-60) / df["close"] - 1}).dropna())
    a = pd.concat(frames)
    b = pd.cut(a["score"], [-1, 30, 50, 65, 80, 101], labels=["0-30", "31-50", "51-65", "66-80", "81-100"])
    g = a.groupby(b, observed=True)
    return pd.DataFrame({"樣本數": g.size(), "20日平均%": g["r20"].mean() * 100, "60日平均%": g["r60"].mean() * 100,
                         "60日中位數%": g["r60"].median() * 100, "60日上漲機率%": g["r60"].apply(lambda x: (x > 0).mean() * 100)}).round(2)


def revenue_study(px: dict[str, pd.DataFrame], revs: dict[str, pd.Series]) -> tuple[pd.DataFrame, int]:
    rows = []
    n_stocks = 0
    for code, rev in revs.items():
        df = px.get(code)
        if df is None or len(rev) < 24:
            continue
        n_stocks += 1
        yoy = rev.pct_change(12) * 100
        yoy_prev = yoy.shift(1)
        hi12 = rev >= rev.rolling(12).max()
        sig_dates = [df.index[df.index.searchsorted(m + pd.DateOffset(months=1, days=10))]
                     if df.index.searchsorted(m + pd.DateOffset(months=1, days=10)) < len(df) else pd.NaT for m in rev.index]
        sd = pd.Series(sig_dates, index=rev.index)
        ok = sd.notna()
        r20 = (df["close"].shift(-20) / df["close"] - 1).reindex(sd[ok]).values
        r60 = (df["close"].shift(-60) / df["close"] - 1).reindex(sd[ok]).values
        b20, b60 = np.nanmean(r20), np.nanmean(r60)
        conds = {"YoY > 20%": yoy > 20, "YoY > 20% 且加速": (yoy > 20) & (yoy > yoy_prev), "YoY > 50%": yoy > 50,
                 "創 12 月新高": hi12, "YoY 0~20%": (yoy >= 0) & (yoy <= 20), "YoY < 0": yoy < 0, "YoY < -20%": yoy < -20}
        for name, m in conds.items():
            mm = m[ok].fillna(False).values
            if mm.sum() < 3:
                continue
            rows.append({"cond": name, "n": int(mm.sum()), "ex20": (np.nanmean(r20[mm]) - b20) * 100,
                         "ex60": (np.nanmean(r60[mm]) - b60) * 100, "raw60": np.nanmean(r60[mm]) * 100})
    df = pd.DataFrame(rows)
    if df.empty:
        return df, 0
    g = df.groupby("cond", sort=False)
    return pd.DataFrame({"事件數": g["n"].sum(), "20日超額%": g["ex20"].mean(), "60日超額%": g["ex60"].mean(),
                         "60日原始報酬%": g["raw60"].mean(), "60日超額為正的股票比例%": g["ex60"].apply(lambda x: (x > 0).mean() * 100)}).round(2), n_stocks


def company_table(px: dict[str, pd.DataFrame], market: str, revs: dict, insts: dict, meta: pd.DataFrame, valuation: pd.DataFrame | None) -> pd.DataFrame:
    rows = []
    for code, df in px.items():
        m = meta.loc[code] if code in meta.index else None
        val = None
        if valuation is not None and code in valuation.index:
            v = valuation.loc[code]
            val = {"pe": v.get("pe"), "pb": v.get("pb"), "dividend_yield": v.get("dividend_yield")}
        try:
            rows.append(analyze_company(df, code=code, name=(m["name"] if m is not None else ""), market=market.upper(),
                                        industry=(m["industry"] if m is not None else ""), monthly_revenue=revs.get(code),
                                        inst=insts.get(code), valuation=val))
        except Exception as e:  # noqa: BLE001
            print(f"analyze fail {code}: {e}", file=sys.stderr)
    return pd.DataFrame(rows)


def main(market: str) -> None:
    px = load_all(market)
    if market == "tw":
        uni = pd.read_csv(ROOT / "tw_universe.csv", dtype=str).set_index("stock_id")
        meta = pd.DataFrame({"name": uni["stock_name"], "industry": uni["industry_category"]})
        revs, insts = load_revenue_tw(), load_inst_tw()
        valuation = None
        vf = ROOT / "tw_valuation.csv"
        if vf.exists():
            valuation = pd.read_csv(vf, dtype={"code": str}).set_index("code")
    else:
        uni = pd.read_csv(ROOT / "us_universe.csv").set_index("symbol")
        meta = pd.DataFrame({"name": uni["name"], "industry": uni["sector"]})
        revs, insts, valuation = {}, {}, None
    span = f"{min(d.index[0] for d in px.values()).date()} ～ {max(d.index[-1] for d in px.values()).date()}"
    print(f"## {market.upper()} 全市場驗證：{len(px)} 檔，{span}\n")
    print("### 策略比較（每檔獨立回測、扣成本、t+1 開盤成交）\n"); print(strat_table(px, market).reset_index().to_markdown(index=False)); print()
    print("### 流動性分層（50/200 vs 買進持有）\n"); print(liquidity_buckets(px, market).reset_index().to_markdown(index=False)); print()
    print("### 技術分數分桶 vs 未來報酬\n"); print(score_buckets(px).reset_index().to_markdown(index=False)); print()
    if revs:
        tab, n = revenue_study(px, revs)
        print(f"### 月營收事件研究（{n} 檔有月營收資料）\n"); print(tab.reset_index().to_markdown(index=False)); print()
    OUT.mkdir(exist_ok=True)
    comp = company_table(px, market, revs, insts, meta, valuation)
    comp.to_csv(OUT / f"{market}_companies.csv", index=False, encoding="utf-8-sig")
    print(f"\n每家公司分析數據已輸出：analysis/{market}_companies.csv（{len(comp)} 列）\n")
    print("### 目前全市場動作分佈\n"); print(comp["action"].value_counts().to_frame("檔數").reset_index().to_markdown(index=False)); print()
    print("### 綜合分數前 20（僅供示範，非投資建議）\n")
    cols = ["code", "name", "industry", "close", "composite_score", "technical_score", "revenue_yoy_pct", "trend_bull", "action"]
    print(comp.sort_values("composite_score", ascending=False).head(20)[[c for c in cols if c in comp]].to_markdown(index=False))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tw")
