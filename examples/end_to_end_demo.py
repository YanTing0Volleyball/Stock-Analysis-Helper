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
from sah.signals import bollinger_mean_reversion, breakout_signal, regime_filter
from sah.signals.composite import score_to_action, technical_score
from sah.signals.technical import atr_trailing_stop


def regime_switch_strategy(df: pd.DataFrame) -> pd.Series:
    """多頭＋趨勢 → 突破策略；多頭＋盤整 → 布林均值回歸；空頭 → 空手。再套 ATR 移動停損。"""
    reg = regime_filter(df)
    trend_pos = breakout_signal(df)
    mr_pos = bollinger_mean_reversion(df)
    pos = pd.Series(0, index=df.index)
    pos[reg["bull"] & reg["trend"]] = trend_pos[reg["bull"] & reg["trend"]]
    pos[reg["bull"] & ~reg["trend"]] = mr_pos[reg["bull"] & ~reg["trend"]]
    return atr_trailing_stop(df, pos)


def main(path: str) -> None:
    df = load_ohlcv_csv(path)
    pos = regime_switch_strategy(df)
    res = run_backtest(df, pos, cost=TW_STOCK, lot_size=1000)
    summ = performance_summary(res.returns, res.equity, res.trades, res.positions)
    print("== 回測 (regime switch + ATR stop, 台股成本) ==")
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
