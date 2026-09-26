"""
回測框架。
- costs.py   台股／美股交易成本模型（手續費、交易稅、滑價）
- engine.py  單檔向量化回測（目標部位 → 權益曲線、交易明細），訊號 t 日 → t+1 執行
- metrics.py 績效指標（CAGR、Sharpe、Sortino、MDD、勝率、盈虧比、Calmar、曝險）與過度配適檢查
"""
from .costs import CostModel, TW_STOCK, TW_ETF, TW_DAYTRADE, US_STOCK
from .engine import BacktestResult, run_backtest
from .metrics import performance_summary, deflated_sharpe_ratio, walk_forward_splits

__all__ = [
    "CostModel", "TW_STOCK", "TW_ETF", "TW_DAYTRADE", "US_STOCK",
    "BacktestResult", "run_backtest", "performance_summary", "deflated_sharpe_ratio", "walk_forward_splits",
]
