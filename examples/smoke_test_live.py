"""
線上資料來源煙霧測試（需可連外網）。在有網路的機器執行：
    python examples/smoke_test_live.py [--tw] [--us]
每個來源只抓一小段資料，印出筆數與最後一列，失敗會印出例外但不中斷。
本腳本用來確認各官方端點格式是否仍與 sah.data 的解析一致；若某來源失敗，請優先改用同市場的備援來源。
"""
from __future__ import annotations

import argparse
import datetime as dt
import traceback

import pandas as pd

pd.set_option("display.width", 160)


def run(name, fn):
    print(f"\n=== {name} ===")
    try:
        out = fn()
        if isinstance(out, (pd.DataFrame, pd.Series)):
            print(f"rows={len(out)}")
            print(out.tail(3))
        else:
            print(out)
        return True
    except Exception:
        traceback.print_exc(limit=2)
        return False


def tw_tests():
    from sah.data import tw_finmind, tw_mops, tw_tpex, tw_twse

    start = (dt.date.today() - dt.timedelta(days=45)).isoformat()
    last_trading = (pd.Timestamp.today() - pd.tseries.offsets.BDay(2)).date()
    prev_month = (dt.date.today().replace(day=1) - dt.timedelta(days=1))
    results = {
        "TWSE 日K 2330": run("TWSE 日K 2330", lambda: tw_twse.fetch_daily_ohlcv("2330", start)),
        "TWSE 全市場收盤": run("TWSE 全市場收盤", tw_twse.fetch_all_daily_close),
        "TWSE 估值 BWIBBU": run("TWSE 估值 BWIBBU", tw_twse.fetch_valuation_all),
        "TWSE 三大法人": run("TWSE 三大法人", lambda: tw_twse.fetch_institutional(last_trading)),
        "TWSE 融資融券": run("TWSE 融資融券", lambda: tw_twse.fetch_margin(last_trading)),
        "TWSE 即時 MIS": run("TWSE 即時 MIS", lambda: tw_twse.fetch_realtime(["2330", "2317"])),
        "TPEx 日K 6213": run("TPEx 日K 6213", lambda: tw_tpex.fetch_daily_ohlcv("6213", start)),
        "TPEx 全市場": run("TPEx 全市場", tw_tpex.fetch_mainboard_quotes),
        "TPEx 三大法人": run("TPEx 三大法人", lambda: tw_tpex.fetch_institutional(last_trading)),
        "MOPS 月營收": run("MOPS 月營收", lambda: tw_mops.fetch_monthly_revenue(prev_month.year, prev_month.month)),
        "FinMind 日K": run("FinMind 日K", lambda: tw_finmind.fetch_daily_ohlcv("2330", start)),
        "FinMind 法人": run("FinMind 法人", lambda: tw_finmind.fetch_institutional("2330", start)),
        "FinMind 月營收": run("FinMind 月營收", lambda: tw_finmind.fetch_monthly_revenue("2330", "2024-01-01")),
    }
    return results


def us_tests():
    from sah.data import us_edgar, us_fred, us_stooq, us_yahoo
    from sah.sentiment import fetch_rss_headlines

    return {
        "Yahoo 日K AAPL": run("Yahoo 日K AAPL", lambda: us_yahoo.fetch_daily_ohlcv("AAPL", range_="3mo")),
        "Yahoo 台股 2330.TW": run("Yahoo 台股 2330.TW", lambda: us_yahoo.fetch_daily_ohlcv("2330.TW", range_="1mo")),
        "Stooq AAPL": run("Stooq AAPL", lambda: us_stooq.fetch_daily_ohlcv("aapl.us", start="2025-01-01")),
        "EDGAR 基本面 AAPL": run("EDGAR 基本面 AAPL", lambda: us_edgar.fetch_fundamentals_summary("AAPL")),
        "EDGAR 申報 AAPL": run("EDGAR 申報 AAPL", lambda: us_edgar.fetch_recent_filings("AAPL").head(10)),
        "FRED DGS10": run("FRED DGS10", lambda: us_fred.fetch_series("DGS10", start="2025-01-01")),
        "RSS Yahoo AAPL": run("RSS Yahoo AAPL", lambda: fetch_rss_headlines(
            "https://feeds.finance.yahoo.com/rss/2.0/headline?s=AAPL&region=US&lang=en-US", limit=5)),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tw", action="store_true")
    ap.add_argument("--us", action="store_true")
    a = ap.parse_args()
    res = {}
    if a.tw or not (a.tw or a.us):
        res.update(tw_tests())
    if a.us or not (a.tw or a.us):
        res.update(us_tests())
    print("\n===== 結果 =====")
    for k, v in res.items():
        print(f"{'OK  ' if v else 'FAIL'} {k}")
