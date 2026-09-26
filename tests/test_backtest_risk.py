import numpy as np
import pandas as pd
import pytest

from sah.backtest import TW_STOCK, US_STOCK, deflated_sharpe_ratio, performance_summary, run_backtest, walk_forward_splits
from sah.backtest.costs import CostModel
from sah.risk import PortfolioLimits, atr_position_size, kelly_fraction, stop_levels, tw_lot_round, volatility_target_weight
from sah.signals import ma_cross_signal


def test_cost_models():
    assert np.isclose(TW_STOCK.round_trip_pct(), 2 * 0.001425 * 0.6 + 0.003 + 0.001)
    assert TW_STOCK.buy_cost(10_000) >= 20  # 最低手續費
    assert US_STOCK.round_trip_pct() < 0.001


def test_buy_and_hold_matches_benchmark_without_costs(ohlcv):
    zero = CostModel(commission_pct=0, tax_sell_pct=0, slippage_pct=0)
    pos = pd.Series(1, index=ohlcv.index)
    res = run_backtest(ohlcv, pos, cost=zero, fill="close", lot_size=1, initial_capital=1e6)
    # 第 2 天收盤買進，之後應與買進持有（自第 2 天起）完全一致
    ratio = res.equity.iloc[1:] / ohlcv["close"].iloc[1:]
    assert np.allclose(ratio, ratio.iloc[0])


def test_backtest_executes_next_day_and_records_trades(ohlcv):
    pos = ma_cross_signal(ohlcv)
    res = run_backtest(ohlcv, pos, cost=TW_STOCK, lot_size=1000)
    assert len(res.equity) == len(ohlcv)
    assert res.positions.iloc[0] == 0  # 第一天不可能有部位（訊號延後一天）
    assert (res.positions.values[1:] == pos.values[:-1]).all()
    assert not res.trades.empty
    assert {"entry_date", "exit_date", "pnl", "return_pct", "holding_days"} <= set(res.trades.columns)
    summ = performance_summary(res.returns, res.equity, res.trades, res.positions)
    assert 0 <= summ["win_rate_pct"] <= 100
    assert summ["max_drawdown_pct"] <= 0
    assert summ["n_trades"] == len(res.trades)


def test_costs_reduce_equity(ohlcv):
    pos = ma_cross_signal(ohlcv)
    zero = CostModel(commission_pct=0, tax_sell_pct=0, slippage_pct=0)
    free = run_backtest(ohlcv, pos, cost=zero, lot_size=1)
    paid = run_backtest(ohlcv, pos, cost=TW_STOCK, lot_size=1)
    assert paid.equity.iloc[-1] < free.equity.iloc[-1]


def test_short_disallowed_by_default(ohlcv):
    pos = pd.Series(-1, index=ohlcv.index)
    res = run_backtest(ohlcv, pos)
    assert (res.positions == 0).all()


def test_deflated_sharpe_penalizes_many_trials():
    single = deflated_sharpe_ratio(0.1, n_trials=1, n_obs=1000)
    many = deflated_sharpe_ratio(0.1, n_trials=200, n_obs=1000)
    assert single > many


def test_walk_forward_splits(ohlcv):
    splits = list(walk_forward_splits(ohlcv.index, train_years=1, test_years=1))
    assert len(splits) == 2
    for tr, te in splits:
        assert tr[-1] < te[0]


def test_position_sizing():
    r = atr_position_size(capital=1_000_000, risk_pct=0.01, entry=100, atr_value=2.5, atr_mult=2)
    assert r["stop"] == 95 and np.isclose(r["shares"], 2000) and np.isclose(r["position_pct"], 0.2)
    assert tw_lot_round(2999) == 2000 and tw_lot_round(2999, allow_odd_lot=True) == 2999
    assert np.isclose(kelly_fraction(0.55, 2.0, 1.0, fraction=1.0), 0.55 - 0.45 / 2)
    assert kelly_fraction(0.3, 1.0, 1.0) == 0.0
    assert np.isclose(volatility_target_weight(0.15, 0.30), 0.5)
    lv = stop_levels(100, atr_value=6, atr_mult=2, max_loss_pct=0.08)
    assert lv["stop"] == 92 and lv["take_profit"] == 116


def test_portfolio_limits():
    lim = PortfolioLimits()
    assert lim.check({"2330": 0.15, "2317": 0.10}) == []
    issues = lim.check({"2330": 0.25, "2317": 0.30, "2454": 0.30}, sectors={"2330": "半導體", "2454": "半導體", "2317": "電子"})
    assert any("單一上限" in s for s in issues) and any("產業" in s for s in issues)
