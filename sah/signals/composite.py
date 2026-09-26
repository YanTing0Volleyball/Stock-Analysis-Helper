"""
多面向綜合評分。目的：讓終端使用者只看一個 0~100 分與一句建議，背後仍可追溯到各面向分數。

設計原則（詳見 docs/06）：
- 各面向分數先各自正規化到 0~100，再依權重加總；權重依操作週期不同（短線重技術＋籌碼，長線重基本面）。
- 分數只代表「相對有利程度」，不是報酬預測；建議動作需再經風控（sah.risk）決定部位大小。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class CompositeWeights:
    """
    權重依 2026-09 真實資料驗證（docs/09）調整：
    - 台股月營收動能（fundamental_score 內的 revenue_yoy）是最強單一訊號 → 基本面權重上調
    - 法人籌碼僅累計量有微弱效果 → 籌碼權重下修
    - 技術分數在台股有單調預測力、在美股大型股反而略呈均值回歸 → 美股請用 us_large_cap()
    """

    technical: float = 0.35
    fundamental: float = 0.35
    chips: float = 0.15
    sentiment: float = 0.15

    @classmethod
    def short_term(cls) -> "CompositeWeights":
        return cls(technical=0.45, fundamental=0.25, chips=0.15, sentiment=0.15)

    @classmethod
    def long_term(cls) -> "CompositeWeights":
        return cls(technical=0.15, fundamental=0.60, chips=0.10, sentiment=0.15)

    @classmethod
    def us_large_cap(cls) -> "CompositeWeights":
        return cls(technical=0.20, fundamental=0.55, chips=0.10, sentiment=0.15)

    def normalized(self) -> dict[str, float]:
        d = {"technical": self.technical, "fundamental": self.fundamental, "chips": self.chips, "sentiment": self.sentiment}
        tot = sum(d.values())
        return {k: v / tot for k, v in d.items()}


def technical_score(df: pd.DataFrame) -> pd.Series:
    """
    技術面 0~100：由趨勢（收盤 vs MA20/60/200、MA 排列）、動能（RSI 位置）、KD 狀態、MACD 柱方向組成。
    """
    from ..indicators import kd, macd, rsi, sma

    c = df["close"]
    s = pd.Series(0.0, index=df.index)
    ma20, ma60, ma200 = sma(c, 20), sma(c, 60), sma(c, 200)
    s += 15 * (c > ma20) + 15 * (c > ma60) + 15 * (c > ma200)
    s += 10 * ((ma20 > ma60) & (ma60 > ma200))  # 多頭排列
    r = rsi(c, 14)
    s += 15 * ((r > 50) & (r < 70)) + 5 * (r <= 30)  # 健康多頭動能 or 超賣反彈機會
    k = kd(df)
    s += 10 * ((k["k"] > k["d"]) & (k["k"] < 80))
    m = macd(c)
    s += 15 * (m["hist"] > m["hist"].shift(1))
    return s.clip(0, 100)


def fundamental_score(row: pd.Series | dict) -> float:
    """
    基本面 0~100（單一時點）。輸入鍵：pe, pb, roe, revenue_yoy, revenue_yoy_prev, debt_to_equity, f_score, dividend_yield（可缺）。
    """
    r = dict(row)
    s, w = 0.0, 0.0

    def add(cond_score: float, weight: float):
        nonlocal s, w
        s += cond_score * weight
        w += weight

    if not _isnan(r.get("pe")):
        pe = r["pe"]
        add(100 if 0 < pe <= 12 else 70 if pe <= 18 else 40 if pe <= 25 else 10, 15)
    if not _isnan(r.get("roe")):
        add(min(100, max(0, r["roe"] / 0.20 * 100)), 15)
    if not _isnan(r.get("revenue_yoy")):
        # 台股驗證：YoY > 20% 公布後 60 日超額 +2.5%、71% 股票為正；加速再 +0.5%；YoY < 0 為負 → 權重 30
        g = r["revenue_yoy"]
        base = 100 if g >= 20 else 70 if g >= 10 else 50 if g >= 0 else 10
        if not _isnan(r.get("revenue_yoy_prev")) and g > r["revenue_yoy_prev"] and g >= 20:
            base = 100
        elif not _isnan(r.get("revenue_yoy_prev")) and g < r["revenue_yoy_prev"]:
            base = max(0, base - 15)
        add(base, 30)
    if not _isnan(r.get("f_score")):
        add(r["f_score"] / 9 * 100, 20)
    if not _isnan(r.get("debt_to_equity")):
        add(100 if r["debt_to_equity"] < 0.5 else 60 if r["debt_to_equity"] < 1 else 20, 10)
    if not _isnan(r.get("dividend_yield")):
        add(min(100, r["dividend_yield"] / 5 * 100), 10)
    return s / w if w else 50.0


def chips_score(inst_score: pd.Series | None = None, margin_score: pd.Series | None = None) -> pd.Series:
    """籌碼面 0~100：inst_score(-3~3) 與 margin_score(-2~2) 線性映射後平均。"""
    parts = []
    if inst_score is not None:
        parts.append((inst_score + 3) / 6 * 100)
    if margin_score is not None:
        parts.append((margin_score + 2) / 4 * 100)
    if not parts:
        raise ValueError("至少提供一種籌碼分數")
    return pd.concat(parts, axis=1).mean(axis=1).clip(0, 100)


def sentiment_score(mean_sentiment: pd.Series) -> pd.Series:
    """情緒 -1~1 → 0~100。"""
    return ((mean_sentiment.fillna(0) + 1) / 2 * 100).clip(0, 100)


def composite_score(technical: pd.Series | float | None = None, fundamental: pd.Series | float | None = None,
                    chips: pd.Series | float | None = None, sentiment: pd.Series | float | None = None,
                    weights: CompositeWeights | None = None) -> pd.Series | float:
    """
    加權綜合分數 0~100。缺少的面向會被移除並重新正規化權重。
    輸入可為 Series（時間序列）或 float（單一時點）。
    """
    w = (weights or CompositeWeights()).normalized()
    comps = {"technical": technical, "fundamental": fundamental, "chips": chips, "sentiment": sentiment}
    avail = {k: v for k, v in comps.items() if v is not None}
    if not avail:
        raise ValueError("至少需要一個面向分數")
    tot_w = sum(w[k] for k in avail)
    total = None
    for k, v in avail.items():
        term = v * (w[k] / tot_w)
        total = term if total is None else total + term
    return total


def score_to_action(score: float, in_position: bool = False) -> str:
    """
    分數 → 建議動作（帶遲滯，避免頻繁翻轉）：
      未持有：≥65 買進、55~64 觀察、<55 不動
      已持有：≤40 賣出、41~50 減碼、>50 續抱
    門檻依 docs/09 §5：台股 technical_score 66~80 為未來報酬最佳區間，81+ 略降（勿追高，但續抱）。
    """
    if in_position:
        if score <= 40:
            return "賣出"
        if score <= 50:
            return "減碼"
        return "續抱"
    if score >= 65:
        return "買進"
    if score >= 55:
        return "觀察"
    return "不動作"


def _isnan(x) -> bool:
    return x is None or (isinstance(x, float) and np.isnan(x))
