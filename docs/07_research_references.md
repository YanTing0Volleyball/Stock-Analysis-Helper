# 07 研究文獻與實務參考

> 依主題整理，每篇附一句「對本專案的意涵」。年份與作者為記憶整理，引用前請以原文為準。

## 1. 散戶行為與交易成本
- **Barber, B. & Odean, T. (2000).** "Trading Is Hazardous to Your Wealth." *Journal of Finance.* 交易最頻繁的 20% 散戶年報酬低於市場約 6.5%。→ 系統必須限制交易頻率並顯示成本。
- **Barber, Lee, Liu & Odean (2009).** "Just How Much Do Individual Investors Lose by Trading?" *Review of Financial Studies.* 台灣 1995–1999 全市場資料：散戶總損失約 GDP 2.2%，其中約 2/3 來自積極交易；機構（外資）獲利。→ 台股籌碼面跟隨法人有實證基礎。
- **Barber, Lee, Liu & Odean (2014).** "The Cross-Section of Speculator Skill: Evidence from Day Trading." *Journal of Financial Markets.* 台灣當沖者中不到 1% 能持續獲利。→ 本專案不建議當沖策略作為主推。
- **Odean, T. (1998).** "Are Investors Reluctant to Realize Their Losses?" 處分效應。→ 機械化停損。

## 2. 動能與趨勢
- **Jegadeesh, N. & Titman, S. (1993).** "Returns to Buying Winners and Selling Losers." *JF.* 3–12 個月動能。→ `momentum_12_1`。
- **Asness, Moskowitz & Pedersen (2013).** "Value and Momentum Everywhere." *JF.* 價值與動能在全球股市及多資產皆存在且負相關。→ 綜合評分同時納入兩者。
- **Moskowitz, Ooi & Pedersen (2012).** "Time Series Momentum." *JFE.* 12 個月時間序列動能跨 58 種資產成立。→ regime 過濾。
- **Faber, M. (2007).** "A Quantitative Approach to Tactical Asset Allocation." 10 月均線擇時：報酬相近、MDD 大減。→ SMA200 過濾。
- **Brock, Lakonishok & LeBaron (1992).** "Simple Technical Trading Rules and the Stochastic Properties of Stock Returns." *JF.* 均線與突破法則在道瓊 90 年資料有預測力（未計成本）。
- **Park, C.-H. & Irwin, S. (2007).** "What Do We Know About the Profitability of Technical Analysis?" *Journal of Economic Surveys.* 95 篇研究中 56 篇正面；新興市場與期貨較顯著，樣本外常衰退。→ 必須 walk-forward。
- **Novy-Marx, R. (2012).** "Is Momentum Really Momentum?" 動能主要來自 12–7 個月前的報酬。→ 跳過最近一月。

## 3. 價值、品質與基本面
- **Fama, E. & French, K. (1992, 1993).** 三因子（市場、規模、價值）。
- **Fama & French (2015).** 五因子加入獲利能力與投資。→ ROE、資產成長納入評分。
- **Novy-Marx, R. (2013).** "The Other Side of Value: The Gross Profitability Premium." *JFE.* 毛利／總資產與 P/B 一樣有效且互補。
- **Piotroski, J. (2000).** "Value Investing: The Use of Historical Financial Statement Information." *JAR.* F-Score。→ `piotroski_f_score`。
- **Bernard, V. & Thomas, J. (1989).** "Post-Earnings-Announcement Drift." → 月營收／財報驚喜後的漂移。
- **Asquith, Pathak & Ritter (2005).** "Short Interest, Institutional Ownership, and Stock Returns." *JFE.* → 空單特徵。
- **Lakonishok, J. & Lee, I. (2001).** "Are Insider Trades Informative?" *RFS.* 內部人買進（尤其小型股）有資訊。
- **Cohen, Malloy & Pomorski (2012).** "Decoding Inside Information." *JF.* 排除例行交易後的機會型內部人交易預測力更強。

## 4. 台股市場微結構與籌碼
- **Lee, Liu, Roll & Subrahmanyam (2004).** "Order Imbalances and Market Efficiency: Evidence from the Taiwan Stock Exchange." *JFQA.* 委託單不平衡的短期預測力。
- **Chen, Chiang & 多篇台灣財金期刊研究**：外資買賣超與後續報酬正相關、投信季底作帳效應、融資餘額與散戶情緒。→ docs/05 規則來源；正式數字需以本引擎重新驗證。
- 證交所、櫃買中心年報：投資人結構統計（外資持股比重、散戶成交比重）。

## 5. 文字情緒
- **Tetlock, P. (2007).** "Giving Content to Investor Sentiment." *JF.* 媒體悲觀 → 隔日下跌後反轉。
- **Loughran, T. & McDonald, B. (2011).** "When Is a Liability Not a Liability?" *JF.* 財金專用情緒字典。
- **Bollen, Mao & Zeng (2011).** Twitter 情緒與道瓊；後續研究多無法穩定複製。→ 社群只作異常熱度。

## 6. 回測方法與過度配適
- **Bailey, Borwein, López de Prado & Zhu (2014).** "Pseudo-Mathematics and Financial Charlatanism." *Notices of the AMS.* 回測過度配適；Deflated Sharpe Ratio。→ `deflated_sharpe_ratio`。
- **Harvey, Liu & Zhu (2016).** "...and the Cross-Section of Expected Returns." *RFS.* 因子研究需 t > 3。
- **López de Prado, M. (2018).** *Advances in Financial Machine Learning.* Purged K-fold、樣本權重、meta-labeling。→ 後續 ML 擴充參考。
- **Kelly, J. (1956)** 與 **Thorp, E. (2006)** "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market." → 半凱利。

## 7. 實務與開源
- 海龜交易法則（Curtis Faith, *Way of the Turtle*, 2007）：Donchian 突破、ATR 部位、2% 風險。
- 開源回測：`vectorbt`、`backtrader`、`zipline-reloaded`、`bt`；開源因子庫：`alphalens`、`pyfolio`（Quantopian 遺產）。
- 台股開源：`FinMind`（資料＋回測）、`twstock`、`shioaji`（永豐 API）、`fugle-marketdata`。
- 美股開源：`yfinance`、`sec-edgar-downloader`、`edgartools`、`fredapi`、`pandas-ta`／`ta-lib`。
