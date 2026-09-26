# 02 資料來源清單與 CP 值評估

> 原則：**官方免費來源優先**（TWSE／TPEx／MOPS／SEC／FRED），第三方免費整合 API（FinMind）作為統一備援，付費來源只在需要即時逐筆或高頻資料時使用。
> 所有來源皆透過 `sah.data.base.HttpClient` 存取（統一限流、重試、磁碟快取）。
> ⚠️ 本次開發環境無法連外，各端點解析依官方文件實作；正式上線前請在有網路的機器執行 `python examples/smoke_test_live.py` 驗證。

## 1. 台股

| 資料 | 來源 | 費用／限制 | 更新時間 | 模組 | 評價 |
|---|---|---|---|---|---|
| 上市日K（個股） | TWSE `STOCK_DAY`（逐月） | 免費；同 IP 頻繁請求會被暫時封鎖，建議 ≥3 秒/次 | 當日 14:00 後 | `tw_twse.fetch_daily_ohlcv` | ★★★★ 官方、穩定，但抓多年歷史需多次呼叫 |
| 上市全市場收盤 | TWSE OpenAPI `STOCK_DAY_ALL` | 免費、單一請求 | 14:00 後 | `tw_twse.fetch_all_daily_close` | ★★★★★ 每日掃描全市場首選 |
| 本益比／殖利率／淨值比 | TWSE OpenAPI `BWIBBU_ALL` | 免費 | 每日 | `tw_twse.fetch_valuation_all` | ★★★★★ 基本面快速篩選 |
| 三大法人買賣超 | TWSE `T86`；TPEx `insti/dailyTrade` | 免費 | 約 15:00 | `tw_twse.fetch_institutional`、`tw_tpex.fetch_institutional` | ★★★★★ 台股最有價值的籌碼資料 |
| 融資融券 | TWSE `MI_MARGN` | 免費 | 約 15:30~16:00 | `tw_twse.fetch_margin` | ★★★★ |
| 即時報價 | TWSE MIS `getStockInfo.jsp` | 免費、約 5 秒延遲、一次最多約 100 檔；勿高頻輪詢 | 盤中 | `tw_twse.fetch_realtime` | ★★★ 只適合盤中監控，不適合當沖策略 |
| 上櫃日K | TPEx `afterTrading/tradingStock` | 免費；網站 2024 改版，路徑可能再變 | 14:00 後 | `tw_tpex.fetch_daily_ohlcv` | ★★★ 建議以 FinMind 備援 |
| 月營收 | MOPS `t21sc03` 彙總頁 | 免費；頁面 big5、限流嚴格 | 每月 10 日前陸續公布 | `tw_mops.fetch_monthly_revenue` | ★★★★ 波段／長線核心輸入 |
| 財報（損益、資產負債、現金流） | MOPS（表單、難爬）→ 改用 FinMind | FinMind 免費額度足夠 | 季報截止日 | `tw_finmind.fetch_financial_statements` / `fetch_balance_sheet` | ★★★★ |
| 整合 API | **FinMind** `api.finmindtrade.com/api/v4/data` | 免費：未註冊約 300 次/時；註冊 token 600 次/時；Sponsor 方案（約 NT$ 300~/月）更高額度＋即時資料 | 日資料約 16:00~18:00 | `tw_finmind.*` | ★★★★★ **CP 值最高**，欄位乾淨、上市櫃統一；缺點是非官方、需注意同步延遲 |
| 即時／逐筆、下單 | 永豐 **Shioaji**、富果 **Fugle** MarketData/Trading API | 開戶免費使用；Fugle 免費方案有請求限制 | 即時 | 未實作（交易執行屬後續模型） | ★★★★ 進入實盤時再接 |
| 還原權息價 | FinMind `TaiwanStockPriceAdj`；Yahoo `2330.TW` adj_close | 免費 | 日 | `tw_finmind.fetch_daily_ohlcv(adjusted=True)`、`us_yahoo` | 長期回測**必須**使用 |
| 借券賣出、董監持股、股利 | FinMind `TaiwanStockSecuritiesLending`、`TaiwanStockShareholding`、`TaiwanStockDividend` | 免費 | 日／月 | `tw_finmind.fetch_dataset(...)` | ★★★ 進階籌碼 |
| 總經（景氣燈號、CPI、外銷訂單） | 國發會／主計總處 開放資料；FinMind `TaiwanBusinessIndicator` | 免費 | 月 | 未實作（可用 `fetch_dataset`） | ★★ 長線擇時參考 |
| 新聞 | 鉅亨網 RSS、經濟日報 RSS、FinMind `TaiwanStockNews`、MOPS 重大訊息 | 免費 | 即時 | `sentiment.fetch_rss_headlines` | ★★★ 雜訊高，只做事件偵測 |

## 2. 美股

| 資料 | 來源 | 費用／限制 | 模組 | 評價 |
|---|---|---|---|---|
| 日K＋還原價 | **Yahoo Finance chart API**（非官方） | 免費；偶爾 429 或改版；亦可用 `yfinance` 套件 | `us_yahoo.fetch_daily_ohlcv` | ★★★★ 最方便，生產環境需備援 |
| 日K 備援 | **Stooq** CSV | 免費；每日下載次數上限 | `us_stooq.fetch_daily_ohlcv` | ★★★ |
| 基本面（XBRL 全部科目） | **SEC EDGAR companyfacts** | 免費、官方；需含 email 的 User-Agent、≤10 req/s | `us_edgar.fetch_fundamentals_summary` | ★★★★★ 最權威，但科目標籤需對應 |
| 內部人交易 Form 4、13F、8-K | SEC EDGAR submissions／full-text search | 免費；Form 4 明細需解析 XML | `us_edgar.fetch_recent_filings`（索引） | ★★★★ 內部人叢集買進有研究支持 |
| 內部人彙整 | OpenInsider（網頁匯出） | 免費、非官方 | 未實作 | ★★★ |
| 空單餘額 | FINRA 半月報；Yahoo quoteSummary `shortPercentOfFloat` | 免費 | `chips.us_flow.short_interest_features`（計算） | ★★★ |
| 總經 | **FRED** | 免費；官方 API 需免費 key，CSV 端點不需 | `us_fred.fetch_series` | ★★★★★ |
| 選擇權 Put/Call、VIX | CBOE 每日 CSV；FRED `VIXCLS` | 免費 | `us_fred.fetch_series("VIXCLS")` | ★★★ 市場情緒 |
| 即時／分鐘 K | Alpha Vantage（免費 25 次/日）、Polygon（免費 5 次/分、延遲 15 分）、Finnhub（免費 60 次/分）、Tiingo（免費 500 次/時） | 免費額度僅供開發 | 未實作 | 付費約 US$ 30~200/月；**波段策略不需要** |
| 付費一站式 | EODHD（約 US$ 20~80/月）、Polygon Starter（US$ 29/月）、Financial Modeling Prep | 含全球（含台股）日K與基本面 | 未實作 | ★★★★ 若要同時覆蓋台美股且省維護，EODHD CP 值最好 |
| 新聞 | Yahoo Finance RSS、Google News RSS、SEC 8-K | 免費 | `sentiment.fetch_rss_headlines` | ★★★ |
| 社群 | Reddit API（免費額度）、StockTwits | 需註冊 | 未實作 | ★★ 研究顯示預測力弱，僅作異常熱度警示 |

## 3. 選型建議（依開發階段）

1. **MVP／回測研究**：FinMind（台）＋ Yahoo（美）＋ EDGAR（美基本面）＋ TWSE OpenAPI（台估值）。全部免費，一天更新一次即可。
2. **每日推播上線**：加上 TWSE T86／MI_MARGN 直連（避免 FinMind 延遲）、MOPS 月營收；FinMind 註冊 token。
3. **實盤下單**：接 Shioaji（台）與 IBKR API 或複委託券商 API（美）；即時資料改由券商提供，成本為零。
4. **付費升級時機**：當需要 (a) 分鐘 K 回測、(b) 逐筆成交、(c) 一個 API 同時覆蓋台美股，再考慮 FinMind Sponsor、Fugle 付費方案或 EODHD。

## 4. 資料品質檢查（每日流程必做）

- `sah.schema.validate_ohlcv`：NaN、high/low 矛盾、非正價格、日期未排序。
- 跨來源一致性：隨機抽 5 檔比對 TWSE 與 FinMind 收盤價，差異 > 0.5% 告警。
- 停牌／處置股：成交量為 0 或缺日 → 排除短線名單。
- 除權息日：比對還原價與原始價差異，確認還原有效。
- 快取 TTL：歷史日K 30 天、當月 12 小時、估值 1 小時、即時 0。

## 5. 法律與使用條款

- TWSE／TPEx 資料可免費使用但**不得作為即時轉播營利**；商業 APP 若顯示即時報價需向交易所申請資訊使用授權，或透過已授權券商 API 取得。
- Yahoo Finance 非官方 API 無 SLA，且其條款不允許商業再散布；商業版建議改付費來源。
- SEC EDGAR 要求 User-Agent 帶聯絡資訊（`SAH_USER_AGENT` 環境變數）。
