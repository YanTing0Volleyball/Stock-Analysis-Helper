"""
全域設定：API 金鑰、快取路徑、HTTP 行為。金鑰一律從環境變數讀取，不寫進程式碼。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    cache_dir: Path = field(default_factory=lambda: Path(os.getenv("SAH_CACHE_DIR", "~/.sah_cache")).expanduser())
    # SEC 規定 User-Agent 必須包含聯絡方式（公司/姓名 email），否則會被拒絕。
    user_agent: str = os.getenv("SAH_USER_AGENT", "StockAnalysisHelper/0.2 (contact: set SAH_USER_AGENT)")
    timeout: float = float(os.getenv("SAH_HTTP_TIMEOUT", "20"))
    # 對同一主機的最小請求間隔（秒），避免被封鎖。TWSE 建議 >= 3 秒。
    min_interval: dict[str, float] = field(
        default_factory=lambda: {
            "www.twse.com.tw": 3.0,
            "mis.twse.com.tw": 1.0,
            "www.tpex.org.tw": 3.0,
            "mops.twse.com.tw": 5.0,
            "mopsov.twse.com.tw": 5.0,
            "data.sec.gov": 0.15,  # SEC 上限 10 req/s
            "api.finmindtrade.com": 0.5,
        }
    )
    finmind_token: str | None = os.getenv("FINMIND_TOKEN")
    fred_api_key: str | None = os.getenv("FRED_API_KEY")


settings = Settings()
