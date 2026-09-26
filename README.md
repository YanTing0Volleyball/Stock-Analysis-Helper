# Stock-Analysis-Helper

台股／美股買賣時機建議系統的**量化分析核心**：資料擷取、技術／基本／籌碼／情報面指標、訊號與綜合評分、回測與風控。
目標是讓後續的量化交易程式或手機 APP 只需呼叫 `sah` 套件，就能得到「分數＋建議動作＋停損＋建議股數」。

## 快速開始

```bash
pip install -e .
pytest -q                                   # 離線單元測試
python examples/end_to_end_demo.py          # 離線示範（合成資料）
python -m sah.cli analyze  --csv examples/sample_ohlcv.csv
python -m sah.cli backtest --csv examples/sample_ohlcv.csv --strategy kd --market TW
python examples/smoke_test_live.py          # 有網路時驗證所有資料來源
```

## 專案結構

```
sah/               核心套件（見 docs/08 介面規格）
  data/            TWSE / TPEx / MOPS / FinMind / Yahoo / Stooq / SEC EDGAR / FRED / 本機 CSV
  indicators/      SMA EMA MACD ADX RSI KD 布林 ATR OBV VWAP ...
  fundamentals/    PE PB ROE F-Score 篩選器
  chips/           三大法人、融資融券、內部人、空單
  sentiment/       新聞 RSS 關鍵字情緒
  signals/         策略部位、regime 切換、綜合評分 0~100、動作
  backtest/        成本模型、回測引擎、績效、Deflated Sharpe、walk-forward
  risk/            ATR 部位、凱利、停損停利、投組限制
docs/              研究文件與分析準則（繁體中文）
tests/             pytest
examples/          離線示範、線上煙霧測試、research/（資料下載與驗證腳本）
legacy (根目錄)    原始 KD 爬蟲腳本：main.program.py, KD_*.py, data_update.py, KD_analyze/
```

## 文件

| | |
|---|---|
| [00 總覽](docs/00_overview.md) | 結論、架構、使用者情境 |
| [01 台美股制度差異](docs/01_market_rules_tw_vs_us.md) | 交易時間、漲跌幅、稅費、結算 |
| [02 資料來源](docs/02_data_sources.md) | 免費／付費來源與 CP 值 |
| [03 技術面準則](docs/03_technical_analysis_guidelines.md) | 指標參數、訊號規則、regime |
| [04 基本面準則](docs/04_fundamental_analysis_guidelines.md) | 選股門檻、F-Score、估值 |
| [05 籌碼與情報面](docs/05_chips_sentiment_guidelines.md) | 法人、融資券、內部人、新聞 |
| [06 回測與風控](docs/06_backtest_risk_framework.md) | 回測規範、成本、風控、決策流程 |
| [07 研究文獻](docs/07_research_references.md) | 學術與實務依據 |
| [08 模組介面規格](docs/08_module_interface_spec.md) | 給後續開發模型 |
| [09 真實資料驗證](docs/09_live_validation.md) | 2026-09 以 10 年台美股資料驗證策略與準則，並據此調整 |

## 聲明
所有訊號為歷史統計上的機率優勢，不構成投資建議；使用者需自負投資決策責任。
