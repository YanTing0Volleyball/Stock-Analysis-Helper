"""
HTTP 客戶端：統一處理 rate limit、重試、User-Agent 與磁碟快取。
所有資料來源模組都應透過 get_client() 發送請求，避免各自為政被封鎖。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from ..config import settings


BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


class DataSourceError(RuntimeError):
    """資料來源回傳錯誤或格式不符。"""


class PermanentError(DataSourceError):
    """不應重試的錯誤（4xx：權限不足、參數錯誤、付費方案限制）。"""


class HttpClient:
    def __init__(self, cache_dir: Path | None = None, user_agent: str | None = None):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent or settings.user_agent
        self.cache_dir = Path(cache_dir or settings.cache_dir)
        self._last_call: dict[str, float] = {}

    # ---- rate limit -------------------------------------------------
    def _throttle(self, url: str) -> None:
        host = urlparse(url).netloc
        gap = settings.min_interval.get(host, 0.0)
        last = self._last_call.get(host, 0.0)
        wait = gap - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        self._last_call[host] = time.monotonic()

    # ---- cache ------------------------------------------------------
    def _cache_path(self, url: str, params: dict | None) -> Path:
        key = hashlib.sha1((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
        return self.cache_dir / f"{key}.cache"

    def get(
        self,
        url: str,
        params: dict | None = None,
        *,
        headers: dict | None = None,
        cache_ttl: float | None = None,
        retries: int = 3,
    ) -> requests.Response:
        """
        GET 並回傳 Response。cache_ttl（秒）大於 0 時，會把 body 寫進磁碟快取；
        歷史資料（日K、財報）建議設長 TTL，即時報價不要快取。
        """
        path = self._cache_path(url, params)
        if cache_ttl and path.exists() and (time.time() - path.stat().st_mtime) < cache_ttl:
            resp = requests.Response()
            resp.status_code = 200
            resp._content = path.read_bytes()
            resp.url = url
            return resp

        host = urlparse(url).netloc
        if headers is None or "User-Agent" not in headers:
            # TWSE / TPEx / MOPS 的 WAF 會擋非瀏覽器 UA；SEC 則要求帶聯絡資訊的 UA（settings.user_agent）
            if host.endswith(("twse.com.tw", "tpex.org.tw")):
                headers = {**(headers or {}), "User-Agent": BROWSER_UA}
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                self._throttle(url)
                resp = self.session.get(url, params=params, headers=headers, timeout=settings.timeout)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise DataSourceError(f"HTTP {resp.status_code} from {url}")
                if 400 <= resp.status_code < 500:
                    # 客戶端錯誤（權限、參數）重試無意義，直接帶回伺服器訊息
                    raise PermanentError(f"HTTP {resp.status_code} from {url}: {resp.text[:300]}")
                resp.raise_for_status()
                if b"FOR SECURITY REASONS, THIS PAGE CAN NOT BE ACCESSED" in resp.content[:2000]:
                    # TWSE 系列網站 (MOPS/MIS) 的 WAF 擋頁：非瀏覽器 User-Agent 或雲端 IP 會被拒
                    raise DataSourceError(f"被 WAF 拒絕 (請改用瀏覽器 User-Agent 或非雲端 IP): {url}")
                if cache_ttl:
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(resp.content)
                return resp
            except PermanentError:
                raise
            except (requests.RequestException, DataSourceError) as exc:  # noqa: PERF203
                last_exc = exc
                time.sleep(2**attempt)
        raise DataSourceError(f"請求失敗 ({retries} 次): {url}") from last_exc

    def get_json(self, url: str, params: dict | None = None, **kw: Any) -> Any:
        resp = self.get(url, params, **kw)
        try:
            return resp.json()
        except ValueError as exc:
            raise DataSourceError(f"非 JSON 回應: {url} -> {resp.text[:200]!r}") from exc


_client: HttpClient | None = None


def get_client() -> HttpClient:
    global _client
    if _client is None:
        _client = HttpClient()
    return _client


def to_float(x: Any) -> float:
    """把 '1,234.5'、'--'、'' 之類的字串安全轉成 float（無法轉時回 NaN）。"""
    if x is None:
        return float("nan")
    s = str(x).replace(",", "").replace("+", "").strip()
    if s in ("", "--", "-", "X", "N/A", "除權息", "除息", "除權"):
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return float("nan")
