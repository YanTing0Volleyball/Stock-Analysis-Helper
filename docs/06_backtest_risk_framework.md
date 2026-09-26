# 06 回測規範、風控規則與綜合決策流程

> 對應模組：`sah.backtest`、`sah.risk`、`sah.signals.composite`。**任何策略未通過本章回測規範，不得進入 APP 推薦。**

## 1. 回測規範

### 1.1 引擎假設（`run_backtest`）
- 訊號 t 日收盤計算 → **t+1 日開盤成交**（`fill="open"`）。
- 全額現金、無槓桿；台股 `lot_size=1000`（零股策略設 1）。
- 成本依 `CostModel`：手續費（含最低 20 元）、賣出交易稅、單邊滑價。
- 不模擬漲跌停鎖死、不模擬部分成交；小型股需另加滑價。
- 價格必須為還原權息價。

### 1.2 成本參數
| 模型 | 手續費（單邊） | 賣出稅 | 滑價（單邊） | 來回合計 |
|---|---|---|---|---|
| `TW_STOCK` | 0.0855%（6 折） | 0.3% | 0.05% | **0.571%** |
| `TW_ETF` | 0.0855% | 0.1% | 0.03% | 0.331% |
| `TW_DAYTRADE` | 0.04275%（3 折） | 0.15% | 0.05% | 0.336% |
| `US_STOCK` | 0 | 0.003% | 0.03% | 0.063% |
| `US_SUBBROKER_TW` | 0.25% | 0.003% | 0.03% | 0.563% |

### 1.3 樣本要求
- 至少 **10 年**日資料且涵蓋一次空頭（台股 2008、2011、2015、2020、2022；美股 2008、2020、2022）。
- 至少 **30 檔**標的（或整個指數成分股），不得只回測單一股票。
- 使用**當期**成分股名單避免存活者偏差。

### 1.4 驗證流程
1. In-sample 參數搜尋只在 `walk_forward_splits` 的 train 區間；績效只看 test 串接。
2. 報告 `deflated_sharpe_ratio(observed_sharpe, n_trials, n_obs)`，n_trials = 嘗試過的參數組合數；< 0.95 視為證據不足。
3. 參數敏感度：主要參數 ±20% 時，Sharpe 變動 < 30% 才算穩健。
4. 與買進持有比較：策略需在 **Calmar（CAGR/MDD）** 與 **MDD** 上優於買進持有；CAGR 不一定要贏。

### 1.5 績效指標（`performance_summary`）
CAGR、年化波動、Sharpe、Sortino、MDD（含高低點日期）、Calmar、曝險比例、交易次數、勝率、平均獲利／虧損、盈虧比（profit factor）、期望值、平均持有天數。

**上線門檻（建議）**：Sharpe ≥ 0.8、MDD ≤ 25%、profit factor ≥ 1.5、交易次數 ≥ 100、Deflated SR ≥ 0.95。

## 2. 風控規則（`sah.risk`）

| 層級 | 規則 | 函式 |
|---|---|---|
| 單筆 | 風險 ≤ 資金 1%（積極 2%）；停損 = 進場 − 2×ATR，且 ≤ 8%（台股再加 10% 跳空緩衝於心理預期） | `atr_position_size`, `stop_levels` |
| 單筆 | 停利 ≥ 2× 風險，或改用 2.5×ATR 移動停損讓利潤奔跑 | `stop_levels`, `atr_trailing_stop` |
| 單一標的 | ≤ 20% | `PortfolioLimits.max_single_weight` |
| 產業 | ≤ 40% | `max_sector_weight` |
| 持股數 | ≤ 10（散戶可管理上限） | `max_positions` |
| 總曝險 | regime bull&trend 100% / bull&~trend 60% / ~bull 30% | `regime_filter` + `max_gross_exposure` |
| 波動調整 | 目標年化波動 15%，權重 = 15% / 標的波動 | `volatility_target_weight` |
| 凱利 | 只用半凱利以下；樣本 < 50 筆交易不得用凱利 | `kelly_fraction` |
| 日損失 | 當日虧損 ≥ 3% 停止新開倉 | `max_daily_loss_pct` |
| 回撤熔斷 | 權益自高點回落 15% → 全面減碼 50%；25% → 停止交易並檢討 | `max_drawdown_halt_pct` |

依據：Barber & Odean (2000) 交易最頻繁的散戶年報酬比最少者低約 7%；Odean (1998) 處分效應（賣賺留賠）是散戶主要行為錯誤 → 機械化停損是對策。

## 3. 綜合評分與決策流程（APP 每日輸出）

### 3.1 權重（`CompositeWeights`）
| 面向 | 預設 | 短線 | 長線 |
|---|---|---|---|
| 技術 | 0.40 | 0.50 | 0.20 |
| 基本 | 0.20 | 0.05 | 0.55 |
| 籌碼 | 0.25 | 0.30 | 0.15 |
| 情緒 | 0.15 | 0.15 | 0.10 |

### 3.2 動作映射（`score_to_action`，含遲滯避免洗刷）
| 狀態 | 分數 | 動作 |
|---|---|---|
| 未持有 | ≥ 70 | 買進（附停損價、建議股數） |
| 未持有 | 60～69 | 觀察（加入自選） |
| 已持有 | > 50 | 續抱 |
| 已持有 | 41～50 | 減碼一半 |
| 已持有 | ≤ 40 或觸及停損 | 賣出 |

### 3.3 每日流程（後續系統實作順序）
```
14:00 台股收盤資料到齊（TWSE STOCK_DAY_ALL / T86 / MI_MARGN；FinMind 備援）
  ├─ 資料品質檢查 validate_ohlcv
  ├─ 更新指標 → technical_score, regime_filter
  ├─ 更新籌碼 → institutional_features, margin_features → chips_score
  ├─ 每週更新基本面 → fundamental_score（月營收公布日 1~10 號加跑）
  ├─ 新聞 RSS → sentiment_score
  ├─ composite_score → score_to_action
  ├─ 風控：atr_position_size + PortfolioLimits.check
  └─ 推播：「代號｜分數｜動作｜停損｜股數｜一句理由」
05:00/04:00 美股收盤後同流程（Yahoo/EDGAR/FRED）
```

### 3.4 輸出範例
```json
{"symbol":"2330","date":"2025-09-25","score":74,"action":"買進",
 "components":{"technical":78,"fundamental":70,"chips":80,"sentiment":55},
 "regime":{"bull":true,"trend":true},
 "risk":{"entry":1040,"stop":1000,"take_profit":1120,"shares":1000,"position_pct":0.10},
 "reasons":["收盤站上 20/60/200 日均線且多頭排列","外資連 4 日買超","月營收 YoY +30%"]}
```

## 4. 已知限制與後續工作
- 引擎為單檔；多檔投組回測（同時考慮資金分配與相關性）需在後續以 `run_backtest` 為基礎擴充，或接 `vectorbt`／`backtrader`。
- 未模擬漲跌停無法成交與流動性衝擊；小型股請加滑價 0.1～0.3%。
- 綜合評分權重為專家預設，**尚未以本引擎在全市場資料上校準**；上線前必須用 10 年資料驗證 `score ≥ 70` 組合的前瞻報酬顯著高於 `score < 40`。
