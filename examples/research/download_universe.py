"""
全市場資料下載（gitignore 目錄 examples/research/data/universe/）。
- 台股：FinMind TaiwanStockInfo 取上市(twse)+上櫃(tpex) 4 碼普通股（排除 ETF/ETN/存託憑證/指數/興櫃），價格用 Yahoo 還原價。
- 美股：S&P 500 現行成分股（Wikipedia），價格用 Yahoo。
- 台股月營收：MOPS 全市場彙總頁（上市+上櫃，逐月）。
- 台股法人：FinMind 逐檔（受免費額度限制，只抓成交量前 N 檔，N 由 --inst-top 指定）。
    python examples/research/download_universe.py prices_tw | prices_us | revenue | inst
"""
from __future__ import annotations

import concurrent.futures as cf
import io
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from sah.data import tw_finmind, tw_mops, us_yahoo
from sah.data.local_csv import save_ohlcv_csv

ROOT = Path(__file__).parent / "data" / "universe"
START = "2012-01-01"


def tw_universe() -> pd.DataFrame:
    info = pd.read_csv(Path(__file__).parent / "data" / "tw_stock_info.csv", dtype=str)
    info = info[info["type"].isin(["twse", "tpex"])]
    info = info[info["stock_id"].str.fullmatch(r"\d{4}")]
    bad = ("ETF", "ETN", "存託憑證", "Index", "所有證券", "指數", "受益證券", "創新板")
    info = info[~info["industry_category"].fillna("").str.contains("|".join(bad))]
    info = info.drop_duplicates("stock_id")
    return info[["stock_id", "stock_name", "type", "industry_category"]].reset_index(drop=True)


def sp500() -> pd.DataFrame:
    html = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
    t = pd.read_html(io.StringIO(html), flavor="lxml")[0]
    t = t.rename(columns={"Symbol": "symbol", "Security": "name", "GICS Sector": "sector", "GICS Sub-Industry": "sub_industry"})
    t["symbol"] = t["symbol"].str.replace(".", "-", regex=False)
    return t[["symbol", "name", "sector", "sub_industry"]]


def _dl(symbol: str, out: Path) -> str:
    if out.exists():
        return "skip"
    try:
        df = us_yahoo.fetch_daily_ohlcv(symbol, start=START)
        if len(df) < 250:
            return "short"
        save_ohlcv_csv(df, out)
        return "ok"
    except Exception as e:  # noqa: BLE001
        return f"fail:{str(e)[:60]}"


def prices(market: str) -> None:
    d = ROOT / f"px_{market}"
    d.mkdir(parents=True, exist_ok=True)
    if market == "tw":
        uni = tw_universe()
        uni.to_csv(ROOT / "tw_universe.csv", index=False)
        jobs = [(f"{r.stock_id}.{'TW' if r.type == 'twse' else 'TWO'}", d / f"{r.stock_id}.csv") for r in uni.itertuples()]
    else:
        uni = sp500()
        uni.to_csv(ROOT / "us_universe.csv", index=False)
        jobs = [(s, d / f"{s}.csv") for s in uni["symbol"]]
    print(f"{market}: {len(jobs)} symbols")
    stats: dict[str, int] = {}
    with cf.ThreadPoolExecutor(3) as ex:
        for i, res in enumerate(ex.map(lambda j: _dl(*j), jobs)):
            key = res.split(":")[0]
            stats[key] = stats.get(key, 0) + 1
            if i % 100 == 0:
                print(i, stats, flush=True)
    print("done", stats)


def revenue() -> None:
    """MOPS 全市場月營收。MOPS WAF 對密集請求會封 IP 數小時：每次請求間隔 10 秒，連續 3 次被擋即停止。"""
    d = ROOT / "revenue"
    d.mkdir(parents=True, exist_ok=True)
    today = pd.Timestamp.today()
    waf_fail = 0
    for y in range(2013, today.year + 1):
        for m in range(1, 13):
            if pd.Timestamp(y, m, 1) >= today.replace(day=1):
                break
            for board in ("sii", "otc"):
                f = d / f"{board}_{y}_{m:02d}.csv"
                if f.exists():
                    continue
                try:
                    tw_mops.fetch_monthly_revenue(y, m, board).to_csv(f)
                    print("ok", f.name, flush=True)
                    waf_fail = 0
                except Exception as e:  # noqa: BLE001
                    print("FAIL", f.name, str(e)[:80], flush=True)
                    if "WAF" in str(e) or "請求失敗" in str(e):
                        waf_fail += 1
                        if waf_fail >= 3:
                            print("MOPS 連續被擋，停止；請稍後再執行", flush=True)
                            return
                time.sleep(10)


def revenue_finmind() -> None:
    """備援：FinMind 逐檔月營收（免費 300 次/小時 → 每 12.5 秒 1 檔）。已有價格檔者優先。"""
    d = ROOT / "revenue_finmind"
    d.mkdir(parents=True, exist_ok=True)
    uni = tw_universe()
    have_px = {f.stem for f in (ROOT / "px_tw").glob("*.csv")}
    codes = sorted(uni["stock_id"], key=lambda c: (c not in have_px, c))
    for i, c in enumerate(codes):
        f = d / f"{c}.csv"
        if f.exists():
            continue
        try:
            df = tw_finmind.fetch_monthly_revenue(c, "2012-01-01")
            df.to_csv(f)
            print("ok", i, c, len(df), flush=True)
        except Exception as e:  # noqa: BLE001
            print("FAIL", c, str(e)[:80], flush=True)
            if "402" in str(e) or "level" in str(e):
                time.sleep(120)
        time.sleep(12.5)


def inst(top_n: int = 400) -> None:
    d = ROOT / "inst"
    d.mkdir(parents=True, exist_ok=True)
    # 以最近 60 日平均成交金額排序取前 top_n
    rows = []
    for f in (ROOT / "px_tw").glob("*.csv"):
        px = pd.read_csv(f, index_col=0, parse_dates=True).tail(60)
        rows.append((f.stem, float((px["close"] * px["volume"]).mean())))
    codes = [c for c, _ in sorted(rows, key=lambda x: -x[1])[:top_n]]
    for i, c in enumerate(codes):
        f = d / f"{c}.csv"
        if f.exists():
            continue
        try:
            tw_finmind.fetch_institutional(c, START).to_csv(f)
            print("ok", i, c, flush=True)
        except Exception as e:  # noqa: BLE001
            print("FAIL", c, str(e)[:80], flush=True)
        time.sleep(12)  # 免費額度 300 次/小時


if __name__ == "__main__":
    what = sys.argv[1]
    {"prices_tw": lambda: prices("tw"), "prices_us": lambda: prices("us"), "revenue": revenue, "revenue_finmind": revenue_finmind,
     "inst": lambda: inst(int(sys.argv[2]) if len(sys.argv) > 2 else 400)}[what]()
