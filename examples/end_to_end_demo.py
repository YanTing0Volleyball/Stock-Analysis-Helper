"""
離線端到端示範：讀 CSV → 指標 → 狀態判斷（regime）→ 策略切換 → ATR 停損 → 回測 → 風控部位建議。
    python examples/end_to_end_demo.py examples/sample_ohlcv.csv
"""
from __future__ import annotations

import sys

import pandas as pd

from sah.backtest import TW_STOCK, performance_summary, run_backtest
from sah.data.local_csv import load_ohlcv_csv
from sah.indicators import atr
from sah.risk import PortfolioLimits, atr_position_size, stop_levels, tw_lot_round
from sah.signals import ma_cross_signal
from sah.signals.composite import score_to_action, technical_score


def core_trend_strategy(df: pd.DataFrame) -> pd.Series:
    """
    核心策略（依 docs/09 驗證結果）：50/200 均線多頭排列持有，否則空手。
    早期版本的「regime 切換（突破／布林）＋ATR 停損」在真實資料上表現不佳，已改為此版本。
    """
    return ma_cross_signal(df, 50, 200)


def main(path: str) -> None:
    df = load_ohlcv_csv(path)
    pos = core_trend_strategy(df)
    res = run_backtest(df, pos, cost=TW_STOCK, lot_size=1000)
    summ = performance_summary(res.returns, res.equity, res.trades, res.positions)
    print("== 回測 (均線 50/200, 台股成本) ==")
    for k in ("total_return_pct", "cagr_pct", "sharpe", "max_drawdown_pct", "n_trades", "win_rate_pct", "profit_factor", "exposure_pct"):
        print(f"  {k:18s} {summ.get(k)}")

    last = df.iloc[-1]
    a = atr(df).iloc[-1]
    score = float(technical_score(df).iloc[-1])
    action = score_to_action(score, in_position=bool(pos.iloc[-1]))
    size = atr_position_size(capital=1_000_000, risk_pct=0.01, entry=last["close"], atr_value=a, atr_mult=2)
    lv = stop_levels(last["close"], a)
    cap_shares = 1_000_000 * PortfolioLimits().max_single_weight / last["close"]  # 單一標的上限 20%
    shares = tw_lot_round(min(size["shares"], cap_shares))
    print("\n== 今日建議 ==")
    print(f"  收盤 {last['close']:.2f}  技術分數 {score:.0f}  建議動作: {action}")
    print(f"  ATR(14) {a:.2f}  停損 {lv['stop']:.2f}  停利 {lv['take_profit']:.2f}")
    print(f"  1% 風險部位: {shares} 股 (約佔資金 {shares * last['close'] / 1_000_000:.1%}，已套用單一標的 20% 上限)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "examples/sample_ohlcv.csv")
