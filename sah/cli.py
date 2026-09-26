"""
命令列入口（示範後續系統如何串接各模組）：
  python -m sah.cli analyze --csv data.csv --market TW          # 對單檔 CSV 做技術面評分＋KD 狀態
  python -m sah.cli backtest --csv data.csv --strategy kd       # 回測（kd / macd / ma / breakout / bb）
  python -m sah.cli fetch --market TW --symbol 2330 --start 2023-01-01 --out 2330.csv   # 需網路
"""
from __future__ import annotations

import argparse
import json
import sys

import pandas as pd

from .backtest import TW_STOCK, US_STOCK, performance_summary, run_backtest
from .data.local_csv import load_ohlcv_csv, save_ohlcv_csv
from .indicators import kd
from .signals import (
    bollinger_mean_reversion,
    breakout_signal,
    kd_signal,
    kd_state,
    ma_cross_signal,
    macd_signal,
    regime_filter,
    score_to_action,
)
from .signals.composite import technical_score

STRATEGIES = {
    "kd": kd_signal,
    "macd": macd_signal,
    "ma": ma_cross_signal,
    "breakout": breakout_signal,
    "bb": bollinger_mean_reversion,
}


def cmd_analyze(args: argparse.Namespace) -> None:
    df = load_ohlcv_csv(args.csv)
    k = kd(df)
    state = kd_state(k["k"], k["d"])
    tech = technical_score(df)
    reg = regime_filter(df)
    last = df.index[-1]
    out = {
        "date": str(last.date()),
        "close": float(df["close"].iloc[-1]),
        "kd": {"k": round(float(k["k"].iloc[-1]), 2), "d": round(float(k["d"].iloc[-1]), 2), "state": state.iloc[-1]},
        "technical_score": round(float(tech.iloc[-1]), 1),
        "regime": {"bull": bool(reg["bull"].iloc[-1]), "trend": bool(reg["trend"].iloc[-1])},
        "action": score_to_action(float(tech.iloc[-1])),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_backtest(args: argparse.Namespace) -> None:
    df = load_ohlcv_csv(args.csv)
    pos = STRATEGIES[args.strategy](df)
    cost = TW_STOCK if args.market == "TW" else US_STOCK
    res = run_backtest(df, pos, cost=cost, lot_size=1000 if args.market == "TW" else 1)
    summ = performance_summary(res.returns, res.equity, res.trades, res.positions)
    bench = performance_summary(res.benchmark.pct_change().fillna(0), res.benchmark)
    print(f"策略 {args.strategy}  vs  買進持有")
    for key in ("total_return_pct", "cagr_pct", "sharpe", "max_drawdown_pct"):
        print(f"  {key:20s} {summ.get(key, float('nan')):10.2f}   {bench.get(key, float('nan')):10.2f}")
    for key in ("n_trades", "win_rate_pct", "profit_factor", "exposure_pct"):
        if key in summ:
            v = summ[key]
            print(f"  {key:20s} {v:10.2f}" if isinstance(v, float) else f"  {key:20s} {v:>10}")


def cmd_fetch(args: argparse.Namespace) -> None:
    if args.market == "TW":
        from .data import tw_twse
        df = tw_twse.fetch_daily_ohlcv(args.symbol, args.start, args.end)
    else:
        from .data import us_yahoo
        df = us_yahoo.fetch_daily_ohlcv(args.symbol, start=args.start, end=args.end)
    save_ohlcv_csv(df, args.out)
    print(f"已儲存 {len(df)} 筆至 {args.out}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="sah")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze"); a.add_argument("--csv", required=True); a.add_argument("--market", default="TW")
    b = sub.add_parser("backtest"); b.add_argument("--csv", required=True); b.add_argument("--strategy", choices=STRATEGIES, default="kd"); b.add_argument("--market", default="TW")
    f = sub.add_parser("fetch"); f.add_argument("--market", default="TW"); f.add_argument("--symbol", required=True)
    f.add_argument("--start", required=True); f.add_argument("--end"); f.add_argument("--out", required=True)
    args = p.parse_args(argv)
    {"analyze": cmd_analyze, "backtest": cmd_backtest, "fetch": cmd_fetch}[args.cmd](args)


if __name__ == "__main__":
    main(sys.argv[1:])
