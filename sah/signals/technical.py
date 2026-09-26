"""
技術面訊號。所有函式輸出「目標部位」Series：+1 多、0 空手、-1 放空（多數策略僅回 0/1）。
訊號在 t 日收盤計算，實際成交假設為 t+1 開盤或收盤（由回測引擎處理，避免前視偏誤）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..indicators import adx, atr, bbands, ema, kd, macd, sma


def kd_state(k: pd.Series, d: pd.Series, overbought: float = 80, oversold: float = 20, dull_days: int = 3) -> pd.Series:
    """
    重現原專案的 KD 狀態分類，但以向量化實作、且不使用 look-ahead：
      高檔鈍化 / 低檔鈍化 / 死亡交叉 / 黃金交叉 / 超買 / 超賣 / 中性
    """
    state = pd.Series("中性", index=k.index, dtype=object)
    hi_dull = (k >= overbought).rolling(dull_days).sum() == dull_days
    lo_dull = (k <= oversold).rolling(dull_days).sum() == dull_days
    cross_up = (k > d) & (k.shift(1) <= d.shift(1))
    cross_dn = (k < d) & (k.shift(1) >= d.shift(1))
    state[k >= overbought] = "超買"
    state[k <= oversold] = "超賣"
    state[cross_dn & (k.shift(1) >= overbought)] = "死亡交叉"
    state[cross_up & (k.shift(1) <= oversold)] = "黃金交叉"
    state[hi_dull] = "高檔鈍化"
    state[lo_dull] = "低檔鈍化"
    return state


def kd_signal(df: pd.DataFrame, n: int = 9, oversold: float = 20, overbought: float = 80,
              use_trend_filter: bool = True) -> pd.Series:
    """
    KD 低檔黃金交叉買進、高檔死亡交叉賣出。
    use_trend_filter=True 時只在收盤 > 60 日均線時做多（KD 為逆勢指標，研究顯示搭配趨勢過濾可大幅降低假訊號）。
    """
    kdf = kd(df, n)
    k, d = kdf["k"], kdf["d"]
    buy = (k > d) & (k.shift(1) <= d.shift(1)) & (k.shift(1) < oversold + 10)
    sell = (k < d) & (k.shift(1) >= d.shift(1)) & (k.shift(1) > overbought - 10)
    if use_trend_filter:
        buy &= df["close"] > sma(df["close"], 60)
    return _to_position(buy, sell, df.index)


def macd_signal(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, zero_filter: bool = False) -> pd.Series:
    """
    DIF 上穿 DEA 買、下穿賣。zero_filter=True 只接受零軸上方的黃金交叉。
    2026-09 真實資料驗證（docs/09）：零軸過濾在台美股都**降低**績效（台股 Sharpe 0.18→0.08），故預設關閉。
    """
    m = macd(df["close"], fast, slow, signal)
    buy = (m["macd"] > m["signal"]) & (m["macd"].shift(1) <= m["signal"].shift(1))
    sell = (m["macd"] < m["signal"]) & (m["macd"].shift(1) >= m["signal"].shift(1))
    if zero_filter:
        buy &= m["macd"] > 0
    return _to_position(buy, sell, df.index)


def ma_cross_signal(df: pd.DataFrame, fast: int = 50, slow: int = 200, kind: str = "sma") -> pd.Series:
    """
    均線黃金／死亡交叉。回傳 1（快線在慢線上）/0。
    2026-09 驗證（docs/09）：50/200 是所有測試策略中 Sharpe 最高、盈虧比最高（約 4）、交易最少（10 年約 7 次）者，
    且是唯一在多數台股上 Calmar 勝過買進持有的策略 → 作為**核心趨勢過濾／持有訊號**。台股 20/60 次之。
    """
    f = (sma if kind == "sma" else ema)(df["close"], fast)
    s = (sma if kind == "sma" else ema)(df["close"], slow)
    pos = (f > s).astype(int)
    pos[s.isna()] = 0
    return pos


def breakout_signal(df: pd.DataFrame, entry_n: int = 55, exit_n: int = 20, vol_confirm: float | None = None,
                    adx_min: float | None = None) -> pd.Series:
    """
    通道突破（Donchian／海龜）：收盤創 entry_n 日新高買進，跌破 exit_n 日新低出場。
    vol_confirm：突破日量比需 ≥ 此值（None 不檢查）。adx_min：ADX 需 ≥ 此值。
    2026-09 驗證（docs/09）：量比與 ADX 過濾在台美股都**降低** Sharpe 與 CAGR（漏掉太多有效突破），預設關閉。
    """
    hi = df["close"].shift(1).rolling(entry_n).max()
    lo = df["close"].shift(1).rolling(exit_n).min()
    buy = df["close"] > hi
    if vol_confirm:
        buy &= df["volume"] / df["volume"].shift(1).rolling(20).mean() >= vol_confirm
    if adx_min:
        buy &= adx(df)["adx"] >= adx_min
    sell = df["close"] < lo
    return _to_position(buy, sell, df.index)


def bollinger_mean_reversion(df: pd.DataFrame, n: int = 20, k: float = 2.0, rsi_n: int = 14) -> pd.Series:
    """
    布林下軌均值回歸：收盤跌破下軌後重新站回下軌買進，觸及中軌出場。只在 200 日均線之上做多。
    適合盤整市（ADX < 20），趨勢市應停用（由 regime_filter 控制）。
    """
    bb = bbands(df["close"], n, k)
    below = df["close"].shift(1) < bb["lower"].shift(1)
    buy = below & (df["close"] >= bb["lower"]) & (df["close"] > sma(df["close"], 200))
    sell = df["close"] >= bb["mid"]
    return _to_position(buy, sell, df.index)


def momentum_12_1(close: pd.Series, lookback: int = 252, skip: int = 21) -> pd.Series:
    """
    學術動能因子（Jegadeesh & Titman 1993）：過去 12 個月報酬、跳過最近 1 個月。
    回傳連續值，供橫斷面排名（多檔股票取前 20% 做多）。單檔使用時 >0 視為多頭。
    """
    return close.shift(skip) / close.shift(lookback) - 1


def regime_filter(df: pd.DataFrame, ma_n: int = 200, adx_n: int = 14, adx_trend: float = 25) -> pd.DataFrame:
    """
    市場狀態判斷，供策略切換：
      bull（收盤 > MA200）、trend（ADX > 25）
      建議：bull & trend → 順勢（突破／均線）；bull & ~trend → 均值回歸（KD／布林）；~bull → 空手或減碼。
    """
    ma = sma(df["close"], ma_n)
    a = adx(df, adx_n)["adx"]
    return pd.DataFrame({"bull": df["close"] > ma, "trend": a > adx_trend, "ma": ma, "adx": a})


def atr_trailing_stop(df: pd.DataFrame, position: pd.Series, n: int = 14, mult: float = 2.5) -> pd.Series:
    """
    對既有多頭部位加上 ATR 移動停損：進場後追蹤最高收盤 - mult×ATR，跌破即出場並等待下一次進場訊號。
    """
    a = atr(df, n)
    pos = position.copy().astype(int)
    in_pos = False
    peak = np.nan
    out = []
    for i in range(len(df)):
        p = int(pos.iloc[i])
        c = df["close"].iloc[i]
        if not in_pos:
            if p == 1:
                in_pos, peak = True, c
            out.append(1 if in_pos else 0)
            continue
        peak = max(peak, c)
        stop = peak - mult * a.iloc[i] if not np.isnan(a.iloc[i]) else -np.inf
        if p == 0 or c < stop:
            in_pos = False
            out.append(0)
        else:
            out.append(1)
    return pd.Series(out, index=df.index)


def _to_position(buy: pd.Series, sell: pd.Series, index: pd.Index) -> pd.Series:
    """把離散買／賣事件轉成持有狀態 (0/1)。買後持有到賣出訊號。"""
    sig = pd.Series(np.nan, index=index)
    sig[buy.fillna(False)] = 1.0
    sig[sell.fillna(False)] = 0.0
    return sig.ffill().fillna(0).astype(int)
