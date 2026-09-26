"""
資料擷取層。每個來源模組提供回傳「標準 OHLCV DataFrame」或「標準表格」的函式，
上層（指標／訊號／回測）不需知道資料從哪裡來。

台股：
- tw_twse     證交所 (上市) 日K、三大法人、融資融券、本益比/殖利率/淨值比、即時報價 (MIS)
- tw_tpex     櫃買中心 (上櫃) 日K、三大法人
- tw_mops     公開資訊觀測站 月營收、財報摘要
- tw_finmind  FinMind 整合 API（免費額度，需 token 提升限制）
美股：
- us_yahoo    Yahoo Finance chart API（非官方、免費、含還原價）
- us_stooq    Stooq 日K CSV（免費、備援）
- us_edgar    SEC EDGAR XBRL companyfacts（官方、免費、基本面）
- us_fred     FRED 總經指標（免費、需 API key 或用 CSV 端點）
共用：
- local_csv   本機 CSV 讀寫（快取／離線回測）
"""
from .base import HttpClient, get_client
from .local_csv import load_ohlcv_csv, save_ohlcv_csv

__all__ = ["HttpClient", "get_client", "load_ohlcv_csv", "save_ohlcv_csv"]
