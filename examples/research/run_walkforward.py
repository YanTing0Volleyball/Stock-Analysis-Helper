"""
Walk-forward 參數驗證（docs/06 §1.4 規範的實作）。
- 對每個策略家族定義參數網格；在 train 區間（3 年）以「跨股票 Sharpe 中位數」選最佳參數，於 test 區間（1 年）評估；逐年滾動。
- 比較三者：(a) walk-forward 選參的樣本外績效 (b) 文獻預設參數的同期績效 (c) 買進持有。
- 回報 Deflated Sharpe Ratio（以網格大小為 n_trials）。
用法：python examples/research/run_walkforward.py [tw|us] [max_stocks]
"""
from __future__ import annotations

import itertools
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from sah.backtest import TW_STOCK, US_STOCK, deflated_sharpe_ratio, performance_summary, run_backtest, walk_forward_splits
from sah.data.local_csv import load_ohlcv_csv
from sah.signals import breakout_signal, kd_signal, ma_cross_signal

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent / "data" / "universe"
PPY = {"tw": 245, "us": 252}

GRIDS = {
    "均線交叉": (lambda d, p: ma_cross_signal(d, p[0], p[1]),
             [p for p in itertools.product((10, 20, 50), (60, 100, 150, 200, 250)) if p[0] < p[1]], (50, 200)),
    "KD＋60MA": (lambda d, p: kd_signal(d, n=p[0], oversold=p[1], overbought=100 - p[1], use_trend_filter=True),
               list(itertools.product((9, 14, 21), (15, 20, 25, 30))), (9, 20)),
    "通道突破": (lambda d, p: breakout_signal(d, entry_n=p[0], exit_n=p[1]),
             [p for p in itertools.product((20, 40, 55, 100), (10, 20, 40)) if p[1] < p[0]], (55, 20)),
}


def load_universe(market: str, max_stocks: int | None, min_years: float = 8) -> dict[str, pd.DataFrame]:
    out = {}
    files = sorted((ROOT / f"px_{market}").glob("*.csv"))
    rows = []
    for f in files:
        df = load_ohlcv_csv(f)
        if "adj_close" in df:
            k = df["adj_close"] / df["close"]
            for c in ("open", "high", "low", "close"):
                df[c] = df[c] * k
        df = df.dropna()
        if len(df) >= min_years * PPY[market]:
            rows.append((f.stem, df, float((df["close"] * df["volume"]).tail(250).mean())))
    rows.sort(key=lambda r: -r[2])  # 流動性高者優先（若限制檔數）
    for code, df, _ in rows[: max_stocks or len(rows)]:
        out[code] = df
    return out


def sharpe_of(df: pd.DataFrame, pos: pd.Series, idx: pd.DatetimeIndex, cost, ppy: int) -> float:
    sub = df.loc[idx]
    if len(sub) < 60:
        return np.nan
    res = run_backtest(sub, pos.loc[idx], cost=cost, lot_size=1)
    return performance_summary(res.returns, res.equity, None, res.positions, periods_per_year=ppy)["sharpe"]


def oos_returns(df: pd.DataFrame, pos: pd.Series, idx: pd.DatetimeIndex, cost) -> pd.Series:
    sub = df.loc[idx]
    res = run_backtest(sub, pos.loc[idx], cost=cost, lot_size=1)
    return res.returns


def run(market: str, max_stocks: int | None) -> str:
    px = load_universe(market, max_stocks)
    cost = TW_STOCK if market == "tw" else US_STOCK
    ppy = PPY[market]
    common = None
    for df in px.values():
        common = df.index if common is None else common.union(df.index)
    lines = [f"### {market.upper()}：{len(px)} 檔（資料 ≥ 8 年、依流動性排序取前 {max_stocks or '全部'}）\n"]
    for fam, (make, grid, default) in GRIDS.items():
        # 預先計算每檔每組參數的部位（避免重複）
        pos_cache = {(code, p): make(df, p) for code, df in px.items() for p in grid}
        rows = []
        oos_wf, oos_def, oos_bh = [], [], []
        chosen = []
        for tr, te in walk_forward_splits(common, train_years=3, test_years=1):
            # train：每組參數的跨股票 Sharpe 中位數
            med = {}
            for p in grid:
                sh = [sharpe_of(df, pos_cache[(code, p)], tr.intersection(df.index), cost, ppy) for code, df in px.items()]
                med[p] = np.nanmedian(sh)
            best = max(med, key=lambda k: (np.nan_to_num(med[k], nan=-9)))
            chosen.append(best)
            # test：等權組合日報酬
            def port(p):
                rs = [oos_returns(df, pos_cache[(code, p)], te.intersection(df.index), cost) for code, df in px.items()
                      if len(te.intersection(df.index)) > 20]
                return pd.concat(rs, axis=1).mean(axis=1) if rs else pd.Series(dtype=float)
            bh = pd.concat([df.loc[te.intersection(df.index), "close"].pct_change().fillna(0) for df in px.values()
                            if len(te.intersection(df.index)) > 20], axis=1).mean(axis=1)
            r_wf, r_def = port(best), port(default)
            oos_wf.append(r_wf); oos_def.append(r_def); oos_bh.append(bh)
            rows.append({"test_year": te[0].year, "chosen": str(best), "train_sharpe": round(med[best], 2),
                         "oos_sharpe_wf": _sh(r_wf, ppy), "oos_sharpe_default": _sh(r_def, ppy), "oos_sharpe_bh": _sh(bh, ppy),
                         "oos_ret_wf%": _ret(r_wf), "oos_ret_default%": _ret(r_def), "oos_ret_bh%": _ret(bh)})
        tab = pd.DataFrame(rows)
        all_wf, all_def, all_bh = pd.concat(oos_wf), pd.concat(oos_def), pd.concat(oos_bh)
        n_obs = len(all_wf)
        dsr = deflated_sharpe_ratio(all_wf.mean() / all_wf.std() if all_wf.std() > 0 else 0, n_trials=len(grid), n_obs=n_obs)
        stable = pd.Series(chosen).value_counts().iloc[0] / len(chosen) if chosen else np.nan
        lines.append(f"#### {fam}（網格 {len(grid)} 組，預設 {default}）\n")
        lines.append(tab.to_markdown(index=False))
        lines.append(f"\n串接樣本外（{tab['test_year'].min()}–{tab['test_year'].max()}）："
                     f"WF 選參 Sharpe **{_sh(all_wf, ppy)}**、CAGR {_cagr(all_wf, ppy)}%、MDD {_mdd(all_wf)}%；"
                     f"預設參數 Sharpe **{_sh(all_def, ppy)}**、CAGR {_cagr(all_def, ppy)}%、MDD {_mdd(all_def)}%；"
                     f"買進持有 Sharpe **{_sh(all_bh, ppy)}**、CAGR {_cagr(all_bh, ppy)}%、MDD {_mdd(all_bh)}%。\n"
                     f"最常被選參數佔比 {stable:.0%}（參數穩定度）；Deflated Sharpe Ratio = {dsr:.2f}（≥0.95 才算證據充分）。\n")
    return "\n".join(lines)


def _sh(r: pd.Series, ppy: int) -> float:
    return round(float(r.mean() / r.std() * np.sqrt(ppy)), 2) if len(r) > 2 and r.std() > 0 else np.nan


def _ret(r: pd.Series) -> float:
    return round(float(((1 + r).prod() - 1) * 100), 1)


def _cagr(r: pd.Series, ppy: int) -> float:
    return round(float(((1 + r).prod() ** (ppy / len(r)) - 1) * 100), 1) if len(r) else np.nan


def _mdd(r: pd.Series) -> float:
    eq = (1 + r).cumprod()
    return round(float((eq / eq.cummax() - 1).min() * 100), 1)


if __name__ == "__main__":
    market = sys.argv[1] if len(sys.argv) > 1 else "tw"
    max_stocks = int(sys.argv[2]) if len(sys.argv) > 2 else None
    print(run(market, max_stocks))
