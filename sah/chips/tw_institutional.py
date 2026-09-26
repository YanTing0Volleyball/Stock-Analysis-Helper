"""
台股籌碼面特徵。輸入為 sah.data.tw_finmind.fetch_institutional / fetch_margin 或 TWSE 逐日彙整後的時間序列。

準則摘要（詳見 docs/05；2026-09 以 39 檔台股 10 年資料驗證，見 docs/09 §3）：
- 「連續 N 日買超」**沒有**預測力（外資連 3 日買超後 20 日超額報酬 ≈ 0）；投信連 3 日買超後反而略為落後。
- 有效的是**累計量**：外資 20 日累計買超 > 20 日總成交量 5% → 20 日超額約 +0.3%；累計賣超 > 5% → 約 -0.2%。
  幅度不大，因此籌碼在綜合評分中權重下修為 0.15，定位為「確認」而非主訊號。
- 融資餘額快速增加而股價不漲 → 散戶追高、籌碼轉弱；融資大減且價穩 → 籌碼沉澱。
- 券資比 (short/margin) 高且價漲 → 可能軋空。
"""
from __future__ import annotations

import pandas as pd


def institutional_features(inst: pd.DataFrame, volume: pd.Series | None = None, window: int = 20) -> pd.DataFrame:
    """
    inst 欄位：foreign_net, trust_net, dealer_net, total_net（股）。volume 為對應日期的成交股數（可選）。
    輸出：
      foreign_streak   外資連續買(正)/賣(負)超天數
      trust_streak     投信連續買/賣超天數
      foreign_cum_w    外資 window 日累計買賣超
      total_cum_w      三大法人 window 日累計
      foreign_cum_ratio 外資累計買超 / window 日總成交量（需 volume）
      inst_score       -3~+3 綜合分數（以累計買賣超為主；連續天數僅保留為顯示用欄位）
    """
    out = pd.DataFrame(index=inst.index)

    def streak(s: pd.Series) -> pd.Series:
        sign = s.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        res = []
        run = 0
        for v in sign:
            if v == 0:
                run = 0
            elif run * v > 0:
                run += v
            else:
                run = v
            res.append(run)
        return pd.Series(res, index=s.index)

    out["foreign_streak"] = streak(inst["foreign_net"])
    out["trust_streak"] = streak(inst["trust_net"])
    out["foreign_cum_w"] = inst["foreign_net"].rolling(window, min_periods=1).sum()
    out["total_cum_w"] = inst["total_net"].rolling(window, min_periods=1).sum()
    if volume is not None:
        v = volume.reindex(inst.index)
        out["foreign_cum_ratio"] = out["foreign_cum_w"] / v.rolling(window, min_periods=1).sum()
    score = pd.Series(0, index=inst.index, dtype=int)
    if "foreign_cum_ratio" in out:
        r = out["foreign_cum_ratio"]
        score += (r > 0.05).astype(int) * 2 - (r < -0.05).astype(int) * 2   # 主訊號：外資累計佔量比
    else:
        score += (out["foreign_cum_w"] > 0).astype(int) - (out["foreign_cum_w"] < 0).astype(int)
    score += (out["total_cum_w"] > 0).astype(int) - (out["total_cum_w"] < 0).astype(int)
    out["inst_score"] = score.clip(-3, 3)
    return out


def margin_features(margin: pd.DataFrame, close: pd.Series | None = None, window: int = 20) -> pd.DataFrame:
    """
    margin 欄位：margin_balance, short_balance（張）。
    輸出：margin_chg_pct_w（融資餘額 window 日變化%）、short_margin_ratio（券資比 %）、
          margin_divergence（融資增 > 10% 但股價跌 → True，散戶套牢警訊）、margin_score（-2~+2）。
    """
    out = pd.DataFrame(index=margin.index)
    out["margin_chg_pct_w"] = margin["margin_balance"].pct_change(window) * 100
    out["short_margin_ratio"] = margin["short_balance"] / margin["margin_balance"].replace(0, float("nan")) * 100
    score = pd.Series(0, index=margin.index, dtype=int)
    if close is not None:
        px_chg = close.reindex(margin.index).pct_change(window) * 100
        out["margin_divergence"] = (out["margin_chg_pct_w"] > 10) & (px_chg < 0)
        score -= out["margin_divergence"].astype(int)
        # 融資減、價漲：籌碼沉澱且強勢
        score += ((out["margin_chg_pct_w"] < -5) & (px_chg > 0)).astype(int)
    score += (out["short_margin_ratio"] > 30).astype(int)  # 券資比高，軋空潛力
    out["margin_score"] = score
    return out
