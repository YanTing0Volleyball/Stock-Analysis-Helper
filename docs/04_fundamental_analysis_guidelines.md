# 04 基本面分析準則（長線／波段）

> 對應模組：`sah.fundamentals`、`sah.data.tw_finmind`（財報／月營收）、`sah.data.us_edgar`、`sah.data.tw_twse.fetch_valuation_all`。

## 1. 研究結論摘要

| 因子 | 效果 | 依據 |
|---|---|---|
| **價值**（低 P/B、低 P/E、高 FCF yield） | 長期溢酬，但 2010 年後在美股大幅減弱、在台股與新興市場仍較顯著；需搭配品質避免「便宜的爛公司」 | Fama & French (1992, 2015)；Asness et al. (2013) |
| **品質／獲利能力**（毛利率／總資產、ROE、盈餘穩定） | 穩健且與價值互補 | Novy-Marx (2013)；Fama & French (2015) 五因子 |
| **Piotroski F-Score** | 在低 P/B 股票中，F ≥ 7 vs ≤ 3 年化差距約 7.5%（原研究美股 1976–1996） | Piotroski (2000) |
| **盈餘／營收動能**（PEAD：財報驚喜後漂移） | 財報優於預期後 60 天內續漲；台股**月營收 YoY 加速**具類似效果，且每月可得 | Bernard & Thomas (1989)；台灣月營收研究（多篇本土期刊） |
| **股利** | 高殖利率本身不是超額報酬來源；「殖利率高＋配發率 < 70%＋盈餘成長」才是 | Fama & French；實務 |
| **投資／資產成長** | 資產快速膨脹（大舉擴產、併購）的公司後續報酬偏低 | Fama & French (2015) 投資因子 |

## 2. 選股門檻（預設值，`FundamentalCriteria`）

| 指標 | 台股 | 美股 | 說明 |
|---|---|---|---|
| 本益比 PE | 0 < PE ≤ 20（電子業可放寬 25） | ≤ 25（成長股用 PEG ≤ 1.5） | 虧損公司 PE 無意義，直接排除 |
| 股價淨值比 PB | ≤ 3（金融股 ≤ 1.5） | ≤ 5（科技業無形資產多，PB 參考性低） | |
| ROE | ≥ 12%（連 3 年 ≥ 15% 為優） | ≥ 15% | 需排除高槓桿造成的高 ROE（配合負債比） |
| 營收成長 | 近 3 月月營收 YoY ≥ 0，且加速者加分 | 季營收 YoY ≥ 0 | 台股月營收為核心 |
| 負債／權益 | ≤ 1.0（金融、營建例外） | ≤ 1.0 | |
| F-Score | ≥ 6（≥ 7 優） | ≥ 6 | 每年更新一次 |
| 殖利率（存股模式） | ≥ 4% 且盈餘配發率 ≤ 80%、連續 5 年配息 | 不建議（30% 預扣稅） | |
| 自由現金流收益率 | ≥ 5% 加分 | ≥ 4% 加分 | |
| 流動性 | 60 日均量 ≥ 500 張 | 日均成交額 ≥ US$ 5M | |

## 3. 台股資料取得流程

1. `tw_twse.fetch_valuation_all()` → 全市場 PE／PB／殖利率（每日）→ 第一層快篩。
2. `tw_finmind.fetch_monthly_revenue(id)` → 月營收 YoY／MoM；判斷「YoY 連 3 月為正且遞增」。
3. `tw_finmind.fetch_financial_statements(id)` + `fetch_balance_sheet(id)` → ROE、毛利率、負債比、F-Score 九項輸入。
4. 全部整理成「每列一檔」的表 → `fundamentals.screen()` → `passed` 與 `score`。

## 4. 美股資料取得流程

1. `us_edgar.fetch_fundamentals_summary(ticker)` → 年度 revenue／net_income／EPS／equity／assets／CF／capex／shares。
2. 價格（Yahoo）× shares_out → 市值 → PE、PB、FCF yield。
3. 季度資料用 `facts_to_series(..., forms=("10-Q","10-K"))` 自行組 TTM。
4. 注意 XBRL 標籤差異：營收可能是 `Revenues` 或 `RevenueFromContractWithCustomerExcludingAssessedTax`，已在 `REVENUE_TAGS` 依序嘗試。

## 5. 長線進出場規則（與技術面結合）

- **進場**：基本面 `passed`，且收盤 > SMA200（避免接刀）。分 2～3 批於 60 日均線附近買入。
- **加碼**：月營收 YoY 加速且股價創 60 日新高。
- **減碼／出場**：
  - 基本面惡化：連 2 季 ROE 下滑且月營收 YoY 連 3 月為負。
  - 估值過熱：PE 超過自身 5 年區間 90 百分位。
  - 技術面：跌破 SMA200 且 20 日內未收復 → 減半；MDD 從持有高點回落 25% → 出清。
- **再平衡**：季度；單一持股上限 20%，產業上限 40%（`PortfolioLimits`）。

## 6. 基本面分數（`fundamental_score`）

| 項目 | 權重 | 評分 |
|---|---|---|
| PE | 20 | ≤12：100；≤18：70；≤25：40；其他 10 |
| ROE | 20 | ROE/20% 線性至 100 |
| 營收 YoY | 20 | ≥20%：100；≥10%：70；≥0：50；<0：10 |
| F-Score | 20 | /9 線性 |
| 負債／權益 | 10 | <0.5：100；<1：60；其他 20 |
| 殖利率 | 10 | /5% 線性 |

缺項自動剔除並重新加權；全部缺項回傳 50（中性）。
