import numpy as np
import pandas as pd

from sah.chips import institutional_features, margin_features, insider_features, short_interest_features
from sah.fundamentals import FundamentalCriteria, graham_number, pe_ratio, piotroski_f_score, screen
from sah.sentiment import keyword_sentiment, sentiment_score_series


def test_pe_and_graham():
    assert pe_ratio(100, 5) == 20
    assert np.isnan(pe_ratio(100, -1))
    assert np.isclose(graham_number(5, 40), np.sqrt(22.5 * 5 * 40))


def test_piotroski_perfect_score():
    prev = dict(net_income=5, operating_cf=6, assets=100, long_term_debt=30, current_assets=40, current_liabilities=20,
                shares_out=1000, gross_profit=30, revenue=100)
    cur = dict(net_income=10, operating_cf=15, assets=105, long_term_debt=25, current_assets=50, current_liabilities=20,
               shares_out=1000, gross_profit=40, revenue=120)
    assert piotroski_f_score(cur, prev) == 9


def test_screener():
    table = pd.DataFrame({"pe": [10, 30, 15], "pb": [1.5, 5, 2], "roe": [0.2, 0.05, 0.15],
                          "revenue_yoy": [10, -5, 3], "debt_to_equity": [0.3, 2, 0.8], "f_score": [8, 3, 7]},
                         index=["A", "B", "C"])
    res = screen(table, FundamentalCriteria())
    assert res.loc["A", "passed"] and res.loc["C", "passed"] and not res.loc["B", "passed"]
    assert res["score"].loc["B"] == 0


def test_institutional_streak_and_score():
    idx = pd.bdate_range("2024-01-01", periods=6)
    inst = pd.DataFrame({"foreign_net": [100, 200, 300, -50, -60, -70], "trust_net": [0, 10, 20, 30, 40, 50],
                         "dealer_net": 0}, index=idx)
    inst["total_net"] = inst.sum(axis=1)
    f = institutional_features(inst)
    assert list(f["foreign_streak"]) == [1, 2, 3, -1, -2, -3]
    assert f["trust_streak"].iloc[-1] == 5
    assert f["inst_score"].iloc[2] == 2 and f["inst_score"].iloc[-1] == 1 - 1 + 1


def test_margin_features_divergence():
    idx = pd.bdate_range("2024-01-01", periods=25)
    margin = pd.DataFrame({"margin_balance": np.linspace(1000, 1300, 25), "short_balance": 100.0}, index=idx)
    close = pd.Series(np.linspace(100, 90, 25), index=idx)
    m = margin_features(margin, close, window=20)
    assert bool(m["margin_divergence"].iloc[-1]) is True
    assert m["margin_score"].iloc[-1] == -1


def test_us_flow_features():
    trades = pd.DataFrame({"date": ["2024-05-01", "2024-05-02", "2024-05-03", "2024-02-01"],
                           "insider": ["a", "b", "c", "d"], "type": ["P", "P", "P", "S"], "value": [1e5, 2e5, 3e5, 9e6]})
    f = insider_features(trades, lookback_days=60)
    assert f["buyers"] == 3 and f["cluster_buy"] and f["sell_value"] == 0
    s = short_interest_features(25e6, 100e6, 4e6)
    assert s["short_pct_float"] == 25 and s["squeeze_risk"]


def test_sentiment():
    assert keyword_sentiment("台積電營收創新高 外資買超") > 0
    assert keyword_sentiment("Company misses estimates, shares plunge") < 0
    assert keyword_sentiment("今日天氣晴") == 0
    h = pd.DataFrame({"published": pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-02"], utc=True),
                      "title": ["營收成長", "獲利衰退", "beats estimates"], "link": ""})
    g = sentiment_score_series(h)
    assert g.loc["2024-01-01", "n"] == 2 and g.loc["2024-01-02", "mean_sentiment"] == 1
