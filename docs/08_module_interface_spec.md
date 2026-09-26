# 08 模組介面規格（給後續開發模型）

> 目標讀者：接手開發量化交易程式或手機 APP 後端的模型／工程師。本文件描述**如何呼叫**、**資料契約**、**擴充規則**，不重複解釋金融邏輯（見 docs/03～06）。

## 1. 安裝與環境

```bash
pip install -e .            # 或 pip install -r requirements.txt
export SAH_USER_AGENT="YourApp/1.0 (contact: you@example.com)"   # SEC 必要
export FINMIND_TOKEN=...    # 可選，提高 FinMind 額度
export FRED_API_KEY=...     # 可選
export SAH_CACHE_DIR=~/.sah_cache
pytest -q                   # 33 個離線測試
python examples/smoke_test_live.py   # 有網路時驗證各資料端點
```

## 2. 資料契約

### 2.1 OHLCV（所有價量函式的輸入／輸出）
```
pandas.DataFrame
  index   : DatetimeIndex, name="date", tz-naive, 升冪、不重複
  columns : open, high, low, close, volume (float64; volume=股數)
  optional: turnover, adj_close, transactions
```
建立方式：`sah.schema.standardize_ohlcv(any_df)`；檢查：`sah.schema.validate_ohlcv(df) -> list[str]`。

### 2.2 籌碼時間序列
```
institutional : index=date; foreign_net, trust_net, dealer_net, total_net  (股)
margin        : index=date; margin_balance, short_balance, margin_change, short_change (張)
```
### 2.3 基本面橫斷面表（每列一檔）
```
index=code; 欄位任選: pe, pb, roe, revenue_yoy, debt_to_equity, f_score, dividend_yield, fcf_yield
```
### 2.4 部位訊號
```
pandas.Series, index 與 OHLCV 對齊, 值 0/1 (或 0~1 比例; -1 放空僅美股)
語意：t 日收盤後想持有的目標部位；回測引擎自動於 t+1 執行
```

## 3. 模組 API 一覽

| 模組 | 主要函式 | 輸入 → 輸出 |
|---|---|---|
| `sah.data.tw_twse` | `fetch_daily_ohlcv(code, start, end)` | → OHLCV |
| | `fetch_all_daily_close()` / `fetch_valuation_all()` | → 全市場表 (index=code) |
| | `fetch_institutional(date)` / `fetch_margin(date)` | → 當日全市場籌碼表 |
| | `fetch_realtime(codes)` | → 即時報價表 |
| `sah.data.tw_tpex` | 同上（上櫃） | |
| `sah.data.tw_mops` | `fetch_monthly_revenue(year, month, board)` | → 全市場月營收表 |
| `sah.data.tw_finmind` | `fetch_daily_ohlcv(id, start, end, adjusted)`、`fetch_institutional`、`fetch_margin`、`fetch_monthly_revenue`、`fetch_financial_statements`、`fetch_balance_sheet`、`fetch_dataset(name, ...)` | |
| `sah.data.us_yahoo` | `fetch_daily_ohlcv(symbol, range_/start/end)`、`fetch_quote(symbols)` | → OHLCV(含 adj_close) |
| `sah.data.us_stooq` | `fetch_daily_ohlcv(symbol)` | 備援 |
| `sah.data.us_edgar` | `fetch_fundamentals_summary(ticker)`、`fetch_company_facts`、`facts_to_series`、`fetch_recent_filings` | |
| `sah.data.us_fred` | `fetch_series(series_id, start)` | → Series |
| `sah.indicators` | `sma ema wma macd adx rsi kd roc williams_r bbands atr keltner historical_volatility obv vwap volume_ratio mfi` | Series/DataFrame → Series/DataFrame |
| `sah.fundamentals` | `pe_ratio peg_ratio roe dividend_yield fcf_yield graham_number piotroski_f_score revenue_momentum ...`、`screen(table, FundamentalCriteria)` | |
| `sah.chips` | `institutional_features(inst, volume)`、`margin_features(margin, close)`、`insider_features(trades)`、`short_interest_features(...)` | |
| `sah.sentiment` | `fetch_rss_headlines(url)`、`keyword_sentiment(text)`、`sentiment_score_series(headlines)` | |
| `sah.signals` | `kd_signal macd_signal ma_cross_signal breakout_signal bollinger_mean_reversion` → 部位 Series；`kd_state`、`momentum_12_1`、`regime_filter`、`atr_trailing_stop` | |
| `sah.signals.composite` | `technical_score(df)`、`fundamental_score(row)`、`chips_score(...)`、`sentiment_score(...)`、`composite_score(..., weights)`、`score_to_action(score, in_position)` | |
| `sah.backtest` | `run_backtest(df, position, cost, ...)` → `BacktestResult`；`performance_summary(...)`；`deflated_sharpe_ratio`；`walk_forward_splits`；`CostModel` 與預設 `TW_STOCK TW_ETF TW_DAYTRADE US_STOCK` | |
| `sah.risk` | `atr_position_size fixed_fractional_size kelly_fraction volatility_target_weight stop_levels tw_lot_round PortfolioLimits` | |
| `sah.cli` | `analyze / backtest / fetch` 子命令 | 範例入口 |

## 4. 端到端範例

```python
from sah.data import tw_finmind
from sah.indicators import atr
from sah.chips import institutional_features
from sah.signals import regime_filter, breakout_signal
from sah.signals.composite import technical_score, chips_score, composite_score, score_to_action, CompositeWeights
from sah.risk import atr_position_size, tw_lot_round
from sah.backtest import run_backtest, performance_summary, TW_STOCK

df   = tw_finmind.fetch_daily_ohlcv("2330", "2015-01-01", adjusted=True)
inst = tw_finmind.fetch_institutional("2330", "2015-01-01")

tech  = technical_score(df)
chips = chips_score(institutional_features(inst, df["volume"])["inst_score"]).reindex(df.index).ffill()
score = composite_score(technical=tech, chips=chips, weights=CompositeWeights.short_term())
action = score_to_action(float(score.iloc[-1]), in_position=False)

size = atr_position_size(1_000_000, 0.01, df["close"].iloc[-1], atr(df).iloc[-1])
shares = tw_lot_round(size["shares"])

res = run_backtest(df, breakout_signal(df), cost=TW_STOCK, lot_size=1000)
print(performance_summary(res.returns, res.equity, res.trades, res.positions))
```
離線版本見 `examples/end_to_end_demo.py`。

## 5. 擴充規則

1. **新增資料來源**：在 `sah/data/` 新增模組，對外函式必須回傳 2.1～2.3 的契約格式；透過 `get_client()` 發請求並在 `config.settings.min_interval` 登記主機限流。
2. **新增指標**：放進 `sah/indicators/` 對應類別檔，純函式、不產生訊號、補 `tests/test_indicators.py`。
3. **新增策略**：`sah/signals/technical.py` 新增函式，回傳部位 Series；必須通過 `test_signals_have_no_lookahead` 同款測試；在 `sah/cli.py` 的 `STRATEGIES` 註冊。
4. **調整評分權重／門檻**：只改 `CompositeWeights`、`FundamentalCriteria`、`PortfolioLimits`，不要把數字散落在業務邏輯。
5. **多檔投組回測**：以 `run_backtest` 為單檔核心，外層依日期迴圈分配資金；或轉接 `vectorbt`，但輸入仍用本契約。
6. **服務化**：建議以 FastAPI 包裝 `analyze` 流程，回傳 docs/06 §3.4 的 JSON；排程用 APScheduler／cron，台股 14:30、美股 05:30（台北時間）。
7. **APP 端**：只消費 JSON（score、action、stop、shares、reasons），不做任何計算，確保邏輯單一來源。

## 6. 已知待辦（後續模型接手）
- [x] 在有網路環境執行 `examples/smoke_test_live.py`，修正端點欄位差異（2026-09-26 完成，見 docs/02 §0）。
- [ ] Form 4 XML 解析 → `insider_features` 的輸入表。
- [x] 以 39 檔台股＋30 檔美股 10 年資料做第一輪校準（docs/09）；待擴大至全市場與 walk-forward。
- [ ] 多檔投組回測與相關性控制。
- [ ] 交易日曆（TWSE 休市表、NYSE 假日）模組。
- [ ] 券商 API（Shioaji／IBKR）下單介面，與 `PortfolioLimits.check` 串接為下單前檢查。
