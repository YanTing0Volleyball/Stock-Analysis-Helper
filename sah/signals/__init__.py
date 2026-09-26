"""
訊號層：把指標數值轉成可執行的多空／評分。
- technical.py  單一策略訊號（KD、MACD、均線、突破、動能、均值回歸）；輸出 +1/0/-1 的 position Series
- composite.py  多面向綜合評分（技術＋基本＋籌碼＋情緒），輸出 0~100 分與建議動作
"""
from .composite import CompositeWeights, composite_score, score_to_action
from .technical import (
    bollinger_mean_reversion,
    breakout_signal,
    kd_signal,
    kd_state,
    ma_cross_signal,
    macd_signal,
    momentum_12_1,
    regime_filter,
)

__all__ = [
    "kd_state", "kd_signal", "macd_signal", "ma_cross_signal", "breakout_signal",
    "bollinger_mean_reversion", "momentum_12_1", "regime_filter",
    "CompositeWeights", "composite_score", "score_to_action",
]
