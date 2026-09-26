# 00 總覽：Stock-Analysis-Helper 量化分析準則與模組

> 目的：為「台股／美股買賣時機建議系統」（未來的量化交易程式與手機 APP）建立**可被其他模型直接取用**的分析準則、資料來源與 Python 模組。
> 本文件集是後續開發的「規格書＋研究摘要」，程式碼在 `sah/` 套件。

## 1. 一句話結論

沒有任何指標能穩定預測單日漲跌；散戶能取得的**可持續優勢**來自四件事，本專案所有模組都圍繞這四件事設計：

| 優勢來源 | 研究依據（見 docs/07） | 對應模組 |
|---|---|---|
| **順勢＋動能**（12-1 個月動能、200 日均線之上才做多） | Jegadeesh & Titman 1993；Moskowitz et al. 2012；Faber 2007 | `sah.signals.momentum_12_1`、`regime_filter`、`breakout_signal` |
| **價值＋品質**（低估值、高獲利品質、財務體質改善） | Fama & French 1992/2015；Novy-Marx 2013；Piotroski 2000 | `sah.fundamentals` |
| **少交易、控成本、嚴停損** | Barber & Odean 2000；Barber, Lee, Liu, Odean 2009（台灣資料：散戶年損失約 GDP 2.2%） | `sah.backtest.costs`、`sah.risk` |
| **利用市場結構特有資訊**（台股法人籌碼、美股內部人買進） | 見 docs/05 | `sah.chips` |

「精準且省力」的實作方式：系統每天收盤後自動更新 → 產生 0~100 綜合分數與**一句建議動作**（買進／觀察／續抱／減碼／賣出）→ 附帶停損價與建議股數。使用者不需看圖。

## 2. 架構

```
資料層 sah.data ──► 指標層 sah.indicators / fundamentals / chips / sentiment
                          │
                          ▼
                   訊號層 sah.signals（策略部位 0/1、綜合分數 0~100、動作）
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
     回測 sah.backtest           風控 sah.risk（部位大小、停損、投組限制）
   （成本、績效、過度配適檢查）          │
                                      ▼
                          後續：交易執行 / APP 推播（另一模型開發）
```

- 所有價量資料統一為 `sah.schema.standardize_ohlcv` 格式（index=date，欄位 open/high/low/close/volume）。
- 每一層都是純函式，不含狀態，方便單元測試與被其他語言／服務呼叫（例如以 FastAPI 包裝）。

## 3. 文件索引

| 檔案 | 內容 |
|---|---|
| `01_market_rules_tw_vs_us.md` | 台股 vs 美股交易制度差異（時間、漲跌幅、稅費、結算、當沖規則）與對策略的影響 |
| `02_data_sources.md` | 免費／付費資料來源清單、CP 值、限流、對應模組 |
| `03_technical_analysis_guidelines.md` | 技術指標參數、訊號規則、市場狀態切換、常見錯誤 |
| `04_fundamental_analysis_guidelines.md` | 長線選股準則、台美股門檻差異、F-Score、估值 |
| `05_chips_sentiment_guidelines.md` | 台股籌碼（三大法人、融資券）、美股資金流（內部人、13F、空單）、新聞情緒 |
| `06_backtest_risk_framework.md` | 回測規範、成本模型、績效指標、過度配適防護、風控規則、綜合評分與決策流程 |
| `07_research_references.md` | 學術與實務研究摘要 |
| `08_module_interface_spec.md` | 給後續開發模型的介面規格、資料流、擴充方式 |

## 4. 使用者情境對應

| 使用者 | 週期 | 主要面向 | 建議策略組合（詳 docs/03、06） |
|---|---|---|---|
| 短線（數日～數週） | 日K | 技術 50%＋籌碼 30%＋情緒 15% | regime 切換：趨勢市用突破／MACD；盤整市用 KD／布林均值回歸；一律 ATR 停損 |
| 波段（1～6 個月） | 日K／週K | 技術 40%＋籌碼 25%＋基本 20% | 12-1 動能排名 ＋ 60 日均線過濾 ＋ 法人同向 |
| 長線（1 年以上） | 月營收／季報 | 基本 55%＋技術 20% | 品質＋價值篩選（F-Score ≥ 7、ROE ≥ 15%、PE 合理），200 日均線之下減碼 |

## 5. 重要聲明（需放入 APP）

- 所有訊號為機率優勢，不是保證；歷史回測不代表未來。
- 台股單日 ±10% 漲跌停與美股盤後跳空，都可能讓停損無法在預設價位成交。
- 本專案不提供投資顧問服務；使用者需自負投資決策責任。
