"""
交易成本模型。回測不含成本的策略幾乎都會高估報酬，台股尤其嚴重（來回約 0.4~0.6%）。

台股（2025 年）：
- 手續費 0.1425%，買賣各收一次；多數網路下單折扣 2.8~6 折（此處預設 6 折 → 0.0855%）。
- 證券交易稅：賣出時收 0.3%；ETF 0.1%；現股當沖賣出減半為 0.15%（優惠延長至 2027 年底，請以最新法規為準）。
- 最低手續費每筆 20 元。
美股：
- 多數券商零佣金；賣出時 SEC fee（約 0.0000278 × 成交金額）與 FINRA TAF（每股 0.000166，上限 8.30 美元），合計可忽略。
- 台灣投資人透過複委託約 0.15~0.5% + 最低 15~35 美元，成本結構接近台股，需另設定。
- 滑價：流動性好的大型股單邊 0.02~0.05%，小型股 0.1% 以上；此處以「單邊 bps」表示。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    commission_pct: float          # 單邊手續費（比例）
    tax_sell_pct: float            # 賣出稅
    slippage_pct: float = 0.0005   # 單邊滑價（預設 5 bps）
    min_commission: float = 0.0    # 最低手續費（以交易貨幣計）

    def buy_cost(self, notional: float) -> float:
        return max(notional * self.commission_pct, self.min_commission) + notional * self.slippage_pct

    def sell_cost(self, notional: float) -> float:
        return max(notional * self.commission_pct, self.min_commission) + notional * (self.tax_sell_pct + self.slippage_pct)

    def round_trip_pct(self) -> float:
        """來回總成本比例（不含最低手續費效果）。"""
        return 2 * self.commission_pct + self.tax_sell_pct + 2 * self.slippage_pct


TW_STOCK = CostModel(commission_pct=0.001425 * 0.6, tax_sell_pct=0.003, slippage_pct=0.0005, min_commission=20)
TW_ETF = CostModel(commission_pct=0.001425 * 0.6, tax_sell_pct=0.001, slippage_pct=0.0003, min_commission=20)
TW_DAYTRADE = CostModel(commission_pct=0.001425 * 0.3, tax_sell_pct=0.0015, slippage_pct=0.0005, min_commission=20)
US_STOCK = CostModel(commission_pct=0.0, tax_sell_pct=0.00003, slippage_pct=0.0003, min_commission=0)
US_SUBBROKER_TW = CostModel(commission_pct=0.0025, tax_sell_pct=0.00003, slippage_pct=0.0003, min_commission=0)
