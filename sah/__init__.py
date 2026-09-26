"""
sah — Stock Analysis Helper 量化分析核心套件。

子模組：
- sah.data          資料擷取（台股 TWSE/TPEx/MOPS/FinMind、美股 Yahoo/Stooq/SEC EDGAR/FRED、本機 CSV）
- sah.indicators    技術指標（趨勢、動能、波動、量能）
- sah.fundamentals  基本面指標與篩選
- sah.chips         籌碼面（台股三大法人／融資融券、美股 13F／內部人／空單）
- sah.sentiment     情報面（新聞 RSS 關鍵字情緒）
- sah.signals       訊號產生與綜合評分
- sah.backtest      回測引擎、交易成本、績效指標
- sah.risk          部位大小與停損停利

所有價量資料一律使用 sah.schema 定義的標準欄位 (date, open, high, low, close, volume)。
"""
from .schema import Market, OHLCV_COLUMNS, standardize_ohlcv

__all__ = ["Market", "OHLCV_COLUMNS", "standardize_ohlcv"]
__version__ = "0.2.0"
