"""
技術指標。全部以 pandas 實作，不依賴 TA-Lib；輸入為標準 OHLCV DataFrame 或 Series，輸出對齊原 index。

原則：
- 指標函式**不**產生買賣訊號，只產生數值；訊號邏輯放在 sah.signals。
- 所有函式皆為純函式，不修改輸入。
- 命名：小寫、與常見縮寫一致（sma, ema, macd, rsi, kd, bbands, atr, obv, adx）。
"""
from .momentum import kd, rsi, roc, williams_r
from .trend import adx, ema, macd, sma, wma
from .volatility import atr, bbands, historical_volatility, keltner
from .volume import mfi, obv, volume_ratio, vwap

__all__ = [
    "sma", "ema", "wma", "macd", "adx",
    "rsi", "kd", "roc", "williams_r",
    "bbands", "atr", "keltner", "historical_volatility",
    "obv", "vwap", "volume_ratio", "mfi",
]
