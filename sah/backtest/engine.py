"""
單檔向量化回測引擎。

設計：
- 輸入：標準 OHLCV、目標部位 Series（0/1，或 0~1 的比例；-1 代表放空，僅美股允許）。
- 執行：t 日收盤產生的部位在 t+1 日以 `fill` 價格成交（'open' 預設，或 'close'）。
- 成本：依 CostModel 計算，並在成交時扣除；資金為全額（不加槓桿）。
- 輸出：BacktestResult（equity 曲線、每日報酬、交易明細、曝險）。

限制：不處理除權息（請用還原價）、不模擬漲跌停無法成交（台股 ±10% 限制在 docs 中提醒）。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .costs import CostModel, TW_STOCK


@dataclass
class BacktestResult:
    equity: pd.Series
    returns: pd.Series
    positions: pd.Series
    trades: pd.DataFrame
    benchmark: pd.Series | None = None

    def exposure(self) -> float:
        return float((self.positions != 0).mean())


def run_backtest(df: pd.DataFrame, target_position: pd.Series, *, cost: CostModel = TW_STOCK,
                 initial_capital: float = 1_000_000, fill: str = "open", allow_short: bool = False,
                 lot_size: int = 1) -> BacktestResult:
    """
    參數
    ----
    df               標準 OHLCV（建議用還原價）
    target_position  與 df 對齊的目標部位比例（0~1；-1~0 為放空）
    fill             't+1 open'（預設）或 'close'（t+1 收盤）
    lot_size         台股整股 1000 股；零股可設 1。影響可買股數取整。
    """
    if fill not in ("open", "close"):
        raise ValueError("fill 需為 'open' 或 'close'")
    tp = target_position.reindex(df.index).fillna(0).astype(float)
    if not allow_short:
        tp = tp.clip(lower=0)
    # 訊號延後一天執行，避免 look-ahead
    exec_pos = tp.shift(1).fillna(0)
    price = df[fill].astype(float)
    close = df["close"].astype(float)

    cash = initial_capital
    shares = 0.0
    equity = np.zeros(len(df))
    trades = []
    entry_price = entry_date = None

    for i, (date, target) in enumerate(exec_pos.items()):
        px = price.iloc[i]
        if np.isnan(px):
            equity[i] = cash + shares * (close.iloc[i] if not np.isnan(close.iloc[i]) else 0)
            continue
        current_value = cash + shares * px
        target_value = target * current_value
        target_shares = np.floor(target_value / px / lot_size) * lot_size if lot_size > 1 else target_value / px
        delta = target_shares - shares
        if abs(delta) * px >= 1:  # 忽略微量調整
            notional = abs(delta) * px
            if delta > 0:
                fee = cost.buy_cost(notional)
                cash -= notional + fee
                if shares == 0:
                    entry_price, entry_date = px, date
            else:
                fee = cost.sell_cost(notional)
                cash += notional - fee
                if target_shares == 0 and entry_price is not None:
                    trades.append(
                        {"entry_date": entry_date, "exit_date": date, "entry_price": entry_price, "exit_price": px,
                         "shares": abs(delta), "pnl": (px - entry_price) * abs(delta) - fee,
                         "return_pct": (px / entry_price - 1) * 100,
                         "holding_days": (date - entry_date).days}
                    )
                    entry_price = entry_date = None
            shares = target_shares
        equity[i] = cash + shares * close.iloc[i]

    eq = pd.Series(equity, index=df.index, name="equity")
    rets = eq.pct_change().fillna(0)
    bench = (close / close.iloc[0] * initial_capital).rename("buy_and_hold")
    trades_df = pd.DataFrame(trades)
    return BacktestResult(equity=eq, returns=rets, positions=exec_pos, trades=trades_df, benchmark=bench)
