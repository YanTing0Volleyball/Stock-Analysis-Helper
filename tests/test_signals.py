import numpy as np
import pandas as pd

from sah.indicators import kd
from sah.signals import (
    CompositeWeights,
    bollinger_mean_reversion,
    breakout_signal,
    composite_score,
    kd_signal,
    kd_state,
    ma_cross_signal,
    macd_signal,
    momentum_12_1,
    regime_filter,
    score_to_action,
)
from sah.signals.composite import chips_score, fundamental_score, technical_score
from sah.signals.technical import atr_trailing_stop


def test_all_strategies_return_binary_positions(ohlcv):
    for fn in (kd_signal, macd_signal, ma_cross_signal, breakout_signal, bollinger_mean_reversion):
        pos = fn(ohlcv)
        assert pos.index.equals(ohlcv.index)
        assert set(pos.unique()) <= {0, 1}, fn.__name__


def test_kd_state_labels(ohlcv):
    k = kd(ohlcv)
    st = kd_state(k["k"], k["d"])
    assert set(st.unique()) <= {"中性", "超買", "超賣", "死亡交叉", "黃金交叉", "高檔鈍化", "低檔鈍化"}
    # 鈍化必須是連續 3 日 >= 80
    dull_idx = st[st == "高檔鈍化"].index
    for d in dull_idx[:5]:
        i = k.index.get_loc(d)
        assert (k["k"].iloc[i - 2 : i + 1] >= 80).all()


def test_signals_have_no_lookahead(ohlcv):
    # 把最後 30 天資料改掉，不應影響之前的訊號
    pos_full = macd_signal(ohlcv)
    pos_trunc = macd_signal(ohlcv.iloc[:-30])
    pd.testing.assert_series_equal(pos_full.iloc[:-30], pos_trunc, check_names=False)


def test_momentum_and_regime(ohlcv):
    m = momentum_12_1(ohlcv["close"])
    assert m.notna().sum() == len(ohlcv) - 252
    reg = regime_filter(ohlcv)
    assert set(reg.columns) == {"bull", "trend", "ma", "adx"}


def test_atr_trailing_stop_only_reduces_exposure(ohlcv):
    base = ma_cross_signal(ohlcv)
    stopped = atr_trailing_stop(ohlcv, base)
    assert (stopped <= base).all()


def test_scores_and_actions(ohlcv):
    t = technical_score(ohlcv)
    assert ((t >= 0) & (t <= 100)).all()
    f = fundamental_score({"pe": 10, "roe": 0.25, "revenue_yoy": 25, "f_score": 8, "debt_to_equity": 0.2})
    assert f > 85
    assert fundamental_score({}) == 50.0
    c = chips_score(pd.Series([3, 0, -3]), pd.Series([2, 0, -2]))
    assert list(c.round(1)) == [100.0, 50.0, 0.0]
    total = composite_score(technical=80.0, fundamental=60.0, weights=CompositeWeights.long_term())
    w = CompositeWeights.long_term()
    expected = (80 * w.technical + 60 * w.fundamental) / (w.technical + w.fundamental)
    assert np.isclose(total, expected)
    assert score_to_action(75) == "買進" and score_to_action(35, in_position=True) == "賣出"
    assert score_to_action(55, in_position=True) == "續抱"
