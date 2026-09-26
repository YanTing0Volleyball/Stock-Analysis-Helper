import numpy as np
import pandas as pd

from sah.indicators import adx, atr, bbands, ema, kd, macd, obv, rsi, sma, volume_ratio


def test_sma_ema_basic(ohlcv):
    c = ohlcv["close"]
    assert np.isclose(sma(c, 5).iloc[-1], c.iloc[-5:].mean())
    assert sma(c, 5).isna().sum() == 4
    e = ema(c, 10)
    assert e.notna().sum() == len(c) - 9


def test_kd_range_and_known_case():
    # 單調上漲 → K 接近 100；單調下跌 → 接近 0
    n = 40
    up = pd.DataFrame({"open": np.arange(n), "high": np.arange(n) + 1.0, "low": np.arange(n) - 0.5,
                       "close": np.arange(n) + 0.5, "volume": 1.0}, index=pd.bdate_range("2024-01-01", periods=n))
    k = kd(up)
    assert k["k"].iloc[-1] > 90 and k["d"].iloc[-1] > 85
    assert ((k["k"].dropna() >= 0) & (k["k"].dropna() <= 100)).all()
    down = up.copy()
    for col in ("open", "high", "low", "close"):
        down[col] = 100 - up[col]
    assert kd(down)["k"].iloc[-1] < 10


def test_kd_uses_high_low_not_close():
    # 若用收盤價計算 RSV，最後一天收在區間頂會得到 RSV=100；用 high/low 則 < 100
    n = 12
    df = pd.DataFrame({"open": 10.0, "high": 12.0, "low": 8.0, "close": 10.0, "volume": 1.0},
                      index=pd.bdate_range("2024-01-01", periods=n))
    df.loc[df.index[-1], "close"] = 11.0
    rsv = kd(df)["rsv"].iloc[-1]
    assert np.isclose(rsv, (11 - 8) / (12 - 8) * 100)


def test_rsi_bounds_and_extremes(ohlcv):
    r = rsi(ohlcv["close"]).dropna()
    assert (r >= 0).all() and (r <= 100).all()
    up = pd.Series(np.arange(1, 50, dtype=float))
    assert rsi(up).iloc[-1] == 100


def test_macd_columns(ohlcv):
    m = macd(ohlcv["close"])
    assert set(m.columns) == {"macd", "signal", "hist"}
    assert np.allclose(m["hist"].dropna(), (m["macd"] - m["signal"]).dropna())


def test_bbands_pct_b(ohlcv):
    bb = bbands(ohlcv["close"]).dropna()
    assert (bb["upper"] >= bb["mid"]).all() and (bb["mid"] >= bb["lower"]).all()
    assert bb["bandwidth"].min() > 0


def test_atr_adx_positive(ohlcv):
    assert (atr(ohlcv).dropna() > 0).all()
    a = adx(ohlcv).dropna()
    assert ((a["adx"] >= 0) & (a["adx"] <= 100)).all()


def test_volume_indicators(ohlcv):
    assert len(obv(ohlcv)) == len(ohlcv)
    vr = volume_ratio(ohlcv["volume"]).dropna()
    assert (vr > 0).all()
