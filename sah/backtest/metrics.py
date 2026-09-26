"""
績效指標與過度配適防護。

- performance_summary：CAGR、年化波動、Sharpe、Sortino、MDD、Calmar、勝率、盈虧比、交易次數、曝險
- deflated_sharpe_ratio：Bailey & López de Prado (2014)，校正多次嘗試後的 Sharpe 膨脹
- walk_forward_splits：滾動樣本外切分，避免只用單一區間最佳化參數
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def max_drawdown(equity: pd.Series) -> tuple[float, pd.Timestamp | None, pd.Timestamp | None]:
    """回傳 (MDD 比例為負值, 高點日, 低點日)。"""
    peak = equity.cummax()
    dd = equity / peak - 1
    if dd.empty:
        return 0.0, None, None
    trough = dd.idxmin()
    peak_date = equity.loc[:trough].idxmax()
    return float(dd.min()), peak_date, trough


def performance_summary(returns: pd.Series, equity: pd.Series | None = None, trades: pd.DataFrame | None = None,
                        positions: pd.Series | None = None, periods_per_year: int = 252, rf: float = 0.0) -> dict:
    r = returns.dropna()
    if equity is None:
        equity = (1 + r).cumprod()
    n_years = len(r) / periods_per_year
    total_ret = equity.iloc[-1] / equity.iloc[0] - 1 if len(equity) > 1 else 0.0
    cagr = (1 + total_ret) ** (1 / n_years) - 1 if n_years > 0 and total_ret > -1 else np.nan
    vol = r.std(ddof=1) * math.sqrt(periods_per_year)
    excess = r - rf / periods_per_year
    sharpe = excess.mean() / r.std(ddof=1) * math.sqrt(periods_per_year) if r.std(ddof=1) > 0 else np.nan
    downside = r[r < 0].std(ddof=1)
    sortino = excess.mean() / downside * math.sqrt(periods_per_year) if downside and downside > 0 else np.nan
    mdd, peak_d, trough_d = max_drawdown(equity)
    out = {
        "total_return_pct": total_ret * 100,
        "cagr_pct": cagr * 100 if not np.isnan(cagr) else np.nan,
        "annual_vol_pct": vol * 100,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown_pct": mdd * 100,
        "mdd_peak": peak_d,
        "mdd_trough": trough_d,
        "calmar": (cagr / abs(mdd)) if mdd < 0 and not np.isnan(cagr) else np.nan,
        "n_periods": len(r),
    }
    if positions is not None:
        out["exposure_pct"] = float((positions != 0).mean()) * 100
    if trades is not None and not trades.empty:
        wins = trades[trades["pnl"] > 0]
        losses = trades[trades["pnl"] <= 0]
        out.update(
            {
                "n_trades": len(trades),
                "win_rate_pct": len(wins) / len(trades) * 100,
                "avg_win_pct": wins["return_pct"].mean() if len(wins) else np.nan,
                "avg_loss_pct": losses["return_pct"].mean() if len(losses) else np.nan,
                "profit_factor": wins["pnl"].sum() / abs(losses["pnl"].sum()) if len(losses) and losses["pnl"].sum() != 0 else np.inf,
                "avg_holding_days": trades["holding_days"].mean(),
                "expectancy_pct": trades["return_pct"].mean(),
            }
        )
    else:
        out["n_trades"] = 0
    return out


def deflated_sharpe_ratio(observed_sharpe: float, n_trials: int, n_obs: int, skew: float = 0.0, kurt: float = 3.0,
                          sharpe_variance: float | None = None) -> float:
    """
    Deflated Sharpe Ratio（Bailey & López de Prado 2014）。
    回傳「觀察到的 Sharpe 並非來自多次嘗試選擇效應」的機率（0~1）；< 0.95 視為證據不足。
    observed_sharpe 與 n_obs 皆以「每期」單位（非年化）計算。sharpe_variance 為各次嘗試 Sharpe 的變異數；
    未提供時假設為 observed_sharpe² / n_obs 的粗估。
    """
    if n_trials < 1 or n_obs < 2:
        return np.nan
    var = sharpe_variance if sharpe_variance is not None else max(observed_sharpe**2 / n_obs, 1e-12)
    euler = 0.5772156649
    z1 = _inv_norm(1 - 1 / n_trials)
    z2 = _inv_norm(1 - 1 / (n_trials * math.e))
    sr0 = math.sqrt(var) * ((1 - euler) * z1 + euler * z2)
    num = (observed_sharpe - sr0) * math.sqrt(n_obs - 1)
    den = math.sqrt(1 - skew * observed_sharpe + (kurt - 1) / 4 * observed_sharpe**2)
    return _norm_cdf(num / den) if den > 0 else np.nan


def _inv_norm(p: float) -> float:
    """常態分配反函數（Acklam 近似，誤差 ~1e-9）。"""
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02, 1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02, 6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00, -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p <= 0 or p >= 1:
        return float("inf") if p >= 1 else float("-inf")
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def walk_forward_splits(index: pd.DatetimeIndex, train_years: float = 3, test_years: float = 1, step_years: float | None = None):
    """
    產生 (train_idx, test_idx) 的滾動切分。策略參數只能在 train 上最佳化，績效只看 test 串接結果。
    """
    step_years = step_years or test_years
    start = index[0]
    end = index[-1]
    while True:
        train_end = start + pd.DateOffset(years=int(train_years), months=int((train_years % 1) * 12))
        test_end = train_end + pd.DateOffset(years=int(test_years), months=int((test_years % 1) * 12))
        if train_end >= end:
            break
        train_idx = index[(index >= start) & (index < train_end)]
        test_idx = index[(index >= train_end) & (index < test_end)]
        if len(test_idx) == 0:
            break
        yield train_idx, test_idx
        start = start + pd.DateOffset(years=int(step_years), months=int((step_years % 1) * 12))
