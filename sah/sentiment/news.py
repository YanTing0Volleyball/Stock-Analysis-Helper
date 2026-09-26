"""
新聞情緒（輕量版）。用關鍵字詞典做極簡情緒分數，供後續換成 LLM 或 FinBERT 時保持同一介面。

免費新聞來源（RSS）：
- 台股：鉅亨網 https://news.cnyes.com/rss/cat/tw_stock（如失效改 https://www.cnyes.com/rss）、
        經濟日報 https://money.udn.com/rssfeed/news/1001/5590/5591?ch=money、
        公開資訊觀測站重大訊息（MOPS，需爬表單）、FinMind TaiwanStockNews。
- 美股：Yahoo Finance https://feeds.finance.yahoo.com/rss/2.0/headline?s=AAPL&region=US&lang=en-US、
        SEC 8-K（EDGAR）、Google News RSS https://news.google.com/rss/search?q=AAPL+stock。
- 社群（雜訊高、僅作異常量偵測）：Reddit r/wallstreetbets JSON、PTT Stock 板（需自行爬）。

研究依據：Tetlock (2007)、Loughran & McDonald (2011) 財金專用詞典。中文詞典為本專案自訂精簡版，
後續建議以 FinBERT-Chinese 或 LLM 取代。
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pandas as pd

from ..data.base import get_client

POSITIVE_ZH = ["創新高", "成長", "增加", "獲利", "轉盈", "優於預期", "買超", "調升", "看好", "擴產", "訂單", "大漲", "漲停", "利多", "回升", "強勁"]
NEGATIVE_ZH = ["下修", "衰退", "減少", "虧損", "轉虧", "不如預期", "賣超", "調降", "看淡", "裁員", "砍單", "大跌", "跌停", "利空", "重挫", "疲弱", "警示", "處置"]
POSITIVE_EN = ["beat", "beats", "record", "growth", "upgrade", "upgraded", "raises", "strong", "surge", "rally", "buyback", "outperform", "profit"]
NEGATIVE_EN = ["miss", "misses", "cut", "cuts", "downgrade", "downgraded", "lowers", "weak", "plunge", "slump", "lawsuit", "probe", "recall", "loss", "layoff", "bankruptcy", "underperform"]


def fetch_rss_headlines(url: str, limit: int = 50) -> pd.DataFrame:
    """抓 RSS，回傳 DataFrame: published, title, link。不依賴 feedparser。"""
    resp = get_client().get(url, cache_ttl=900)
    root = ET.fromstring(resp.content)
    rows = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
        rows.append({"published": pd.to_datetime(pub, errors="coerce", utc=True), "title": title, "link": link})
        if len(rows) >= limit:
            break
    return pd.DataFrame(rows)


def keyword_sentiment(text: str) -> float:
    """回傳 -1~+1 的簡易情緒分數：(正詞數 - 負詞數) / (正+負)，無關鍵詞為 0。"""
    t = text.lower()
    pos = sum(t.count(w) for w in POSITIVE_ZH) + len(re.findall(r"\b(" + "|".join(POSITIVE_EN) + r")\b", t))
    neg = sum(t.count(w) for w in NEGATIVE_ZH) + len(re.findall(r"\b(" + "|".join(NEGATIVE_EN) + r")\b", t))
    tot = pos + neg
    return (pos - neg) / tot if tot else 0.0


def sentiment_score_series(headlines: pd.DataFrame, freq: str = "D") -> pd.DataFrame:
    """把標題表彙整成每日：n（則數）、mean_sentiment、abnormal_volume（則數 > 20 日均 ×2）。"""
    if headlines.empty:
        return pd.DataFrame(columns=["n", "mean_sentiment", "abnormal_volume"])
    h = headlines.dropna(subset=["published"]).copy()
    h["score"] = h["title"].map(keyword_sentiment)
    h["date"] = h["published"].dt.tz_convert(None).dt.normalize()
    g = h.groupby("date").agg(n=("score", "size"), mean_sentiment=("score", "mean"))
    g = g.asfreq(freq, fill_value=0) if freq else g
    g["abnormal_volume"] = g["n"] > g["n"].rolling(20, min_periods=5).mean() * 2
    return g
