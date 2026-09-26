"""
部位大小與停損規則。獲利的關鍵不在勝率而在「賠小賺大＋活得夠久」；
研究（Barber & Odean 等）顯示散戶虧損主因是過度交易與不停損，因此本模組是所有策略的必經關卡。

規則摘要（詳見 docs/06）：
- 單筆風險 ≤ 總資金 1~2%（fixed_fractional）；停損距離用 ATR 決定，部位 = 風險金額 / 停損距離。
- 單一標的 ≤ 20%、單一產業 ≤ 40%、總曝險依市場狀態 (regime) 調整。
- Kelly 只用「半凱利」以下；勝率／盈虧比估計誤差大時凱利會過度下注。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def fixed_fractional_size(capital: float, risk_pct: float, entry: float, stop: float) -> float:
    """固定比例風險法：可買股數 = 資金×風險比例 / 每股風險。"""
    per_share_risk = abs(entry - stop)
    if per_share_risk <= 0:
        return 0.0
    return capital * risk_pct / per_share_risk


def atr_position_size(capital: float, risk_pct: float, entry: float, atr_value: float, atr_mult: float = 2.0) -> dict:
    """以 ATR 決定停損與股數。回傳 stop、shares、position_value、position_pct。"""
    stop = entry - atr_mult * atr_value
    shares = fixed_fractional_size(capital, risk_pct, entry, stop)
    value = shares * entry
    return {"stop": stop, "shares": shares, "position_value": value, "position_pct": value / capital if capital else np.nan}


def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float, fraction: float = 0.5) -> float:
    """
    凱利公式 f* = W - (1-W)/R，R = 平均獲利/平均虧損。回傳乘上 fraction（預設半凱利）後的資金比例，下限 0。
    """
    if avg_loss <= 0 or avg_win <= 0:
        return 0.0
    r = avg_win / avg_loss
    f = win_rate - (1 - win_rate) / r
    return max(0.0, f * fraction)


def volatility_target_weight(target_annual_vol: float, asset_annual_vol: float, max_weight: float = 1.0) -> float:
    """波動度目標：權重 = 目標波動 / 標的波動（上限 max_weight）。讓不同波動的標的承擔相同風險。"""
    if asset_annual_vol <= 0:
        return 0.0
    return min(max_weight, target_annual_vol / asset_annual_vol)


def stop_levels(entry: float, atr_value: float, atr_mult: float = 2.0, reward_risk: float = 2.0,
                max_loss_pct: float | None = 0.08) -> dict:
    """
    停損停利：停損 = entry - mult×ATR（且不超過 max_loss_pct）；停利 = entry + reward_risk × 風險距離。
    台股單日 ±10% 限制下，隔日跳空可能穿越停損，max_loss_pct 應視為預期值而非保證。
    """
    stop = entry - atr_mult * atr_value
    if max_loss_pct is not None:
        stop = max(stop, entry * (1 - max_loss_pct))
    risk = entry - stop
    return {"stop": stop, "take_profit": entry + reward_risk * risk, "risk_per_share": risk, "risk_pct": risk / entry}


def tw_lot_round(shares: float, allow_odd_lot: bool = False) -> int:
    """台股整股為 1000 股一張；allow_odd_lot=True 則允許零股（盤中零股 2020/10 起開放）。"""
    if allow_odd_lot:
        return int(np.floor(shares))
    return int(np.floor(shares / 1000) * 1000)


@dataclass
class PortfolioLimits:
    max_single_weight: float = 0.20
    max_sector_weight: float = 0.40
    max_gross_exposure: float = 1.0
    max_positions: int = 10
    risk_per_trade: float = 0.01
    max_daily_loss_pct: float = 0.03   # 當日虧損達此比例停止新開倉
    max_drawdown_halt_pct: float = 0.15  # 權益自高點回落達此比例，全面減碼 50%

    def check(self, weights: dict[str, float], sectors: dict[str, str] | None = None) -> list[str]:
        """回傳違規清單（空清單為通過）。weights 為 {代號: 權重}。"""
        issues = []
        for k, w in weights.items():
            if w > self.max_single_weight + 1e-9:
                issues.append(f"{k} 權重 {w:.1%} 超過單一上限 {self.max_single_weight:.0%}")
        gross = sum(abs(w) for w in weights.values())
        if gross > self.max_gross_exposure + 1e-9:
            issues.append(f"總曝險 {gross:.1%} 超過 {self.max_gross_exposure:.0%}")
        if len([w for w in weights.values() if w != 0]) > self.max_positions:
            issues.append(f"持股數超過 {self.max_positions}")
        if sectors:
            agg: dict[str, float] = {}
            for k, w in weights.items():
                agg[sectors.get(k, "unknown")] = agg.get(sectors.get(k, "unknown"), 0) + w
            for s, w in agg.items():
                if w > self.max_sector_weight + 1e-9:
                    issues.append(f"產業 {s} 權重 {w:.1%} 超過 {self.max_sector_weight:.0%}")
        return issues
