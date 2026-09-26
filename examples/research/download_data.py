"""下載研究資料到 examples/research/data/（gitignore）。台股價格用 Yahoo 還原價（FinMind 還原價需付費）、法人＋月營收用 FinMind；美股用 Yahoo。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

from sah.data import tw_finmind, us_yahoo
from sah.data.local_csv import save_ohlcv_csv

OUT = Path(__file__).parent / "data"
START = "2015-01-01"
# 台股：0050 主要成分 + 幾檔中小型，涵蓋電子/金融/傳產
TW = ["2330", "2317", "2454", "2308", "2303", "2382", "2357", "3711", "2379", "2345", "3034", "2412", "2882", "2881",
      "2891", "2886", "2884", "1301", "1303", "2002", "1216", "2603", "2609", "2615", "9910", "1101", "2207", "2912",
      "3231", "2356", "6505", "1326", "2395", "2327", "2301", "4938", "2408", "3045", "2801", "0050"]
US = ["SPY", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "JPM", "XOM", "JNJ", "PG", "V", "UNH", "HD",
      "COST", "PEP", "KO", "WMT", "CVX", "MRK", "ABBV", "BAC", "CSCO", "INTC", "DIS", "NKE", "MCD", "CAT", "BA", "GE"]


def _tw_px(code: str) -> pd.DataFrame:
    try:
        return us_yahoo.fetch_daily_ohlcv(f"{code}.TW", start=START)
    except Exception:  # noqa: BLE001  上櫃改用 .TWO
        return us_yahoo.fetch_daily_ohlcv(f"{code}.TWO", start=START)


def main(which: str = "all") -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if which in ("all", "tw"):
        for c in TW:
            for kind, fn in [("px", lambda: _tw_px(c)),
                             ("inst", lambda: tw_finmind.fetch_institutional(c, START)),
                             ("rev", lambda: tw_finmind.fetch_monthly_revenue(c, START))]:
                f = OUT / f"tw_{c}_{kind}.csv"
                if f.exists():
                    continue
                try:
                    df = fn()
                    (save_ohlcv_csv(df, f) if kind == "px" else df.to_csv(f, index_label="date"))
                    print("ok", f.name, len(df))
                except Exception as e:  # noqa: BLE001
                    print("FAIL", f.name, str(e)[:120])
                time.sleep(0.6)
    if which in ("all", "us"):
        for s in US:
            f = OUT / f"us_{s}_px.csv"
            if f.exists():
                continue
            try:
                df = us_yahoo.fetch_daily_ohlcv(s, start=START)
                save_ohlcv_csv(df, f)
                print("ok", f.name, len(df))
            except Exception as e:  # noqa: BLE001
                print("FAIL", f.name, str(e)[:120])
            time.sleep(1.0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
