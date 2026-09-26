# analysis/ — 每家公司分析數據

由 `python examples/research/run_universe_validation.py tw|us` 產生，每家公司一列；產生邏輯在 `sah/analysis/company.py::analyze_company`，
APP 後端每日收盤後重跑即可更新。編碼 UTF-8（含 BOM，Excel 可直接開）。

| 欄位 | 說明 |
|---|---|
| code / name / market / industry | 代號、名稱、市場（TW/US）、產業 |
| date / close | 資料最後日期與收盤（還原價） |
| ret_1m_pct / ret_3m_pct / ret_12m_pct | 近 1／3／12 月報酬 % |
| sma50 / sma200 / trend_bull / dist_sma200_pct | 50、200 日均線；`trend_bull` = 收盤 > SMA200 且 SMA50 > SMA200（核心持有條件）；離 200 日線距離 % |
| high_52w_pct | 距 52 週高點 %（0 = 創新高） |
| rsi14 / kd_k / kd_d / kd_state / macd_hist | 動能指標；`kd_state` 為原專案的七種狀態文字 |
| atr14_pct / vol_20d_annual_pct | ATR 佔價 %、20 日年化波動 % |
| avg_turnover_20d | 20 日平均成交金額（流動性過濾用） |
| momentum_12_1_pct | 12-1 月動能 % |
| technical_score | 技術分數 0～100（docs/03 §4） |
| revenue_yoy_pct / revenue_yoy_prev_pct / revenue_signal / revenue_new_12m_high | 最新月營收 YoY、前月 YoY、動能訊號（+1/0/-1）、是否創 12 月新高（台股） |
| foreign_cum20_ratio / inst_score | 外資 20 日累計買賣超 ÷ 20 日成交量、籌碼分數 -3～3（台股，有法人資料者） |
| pe / pb / dividend_yield / fundamental_score | 估值與基本面分數（有資料者） |
| chips_score / composite_score / action | 籌碼分數、綜合分數 0～100、建議動作（買進／觀察／不動作／續抱／減碼／賣出） |
| stop_loss | 建議停損價 = 收盤 − 2×ATR |
| bh_cagr_pct / bh_mdd_pct | 該股資料期間買進持有的 CAGR 與最大回撤 |
| ma50_200_cagr_pct / ma50_200_sharpe / ma50_200_mdd_pct / ma50_200_calmar_vs_bh | 該股用 50/200 均線策略（扣成本）的歷史績效，及 Calmar 是否勝過買進持有（判斷此股是否適合趨勢策略） |
| years_of_data | 資料年數 |

注意：
- `action` 是規則輸出，不是投資建議；缺基本面／籌碼資料時綜合分數只由技術面組成，會偏極端。
- 月營收與法人資料受免費 API 額度限制，並非每檔都有（欄位為空）。
