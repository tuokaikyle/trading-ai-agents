import math

import pandas as pd
import pytest

from trading_ai_agents.data import YahooData, calculate_indicators, clean


@pytest.mark.parametrize("closes, expected", [
    (list(range(1, 21)), 100), (list(range(20, 0, -1)), 0), ([10] * 20, 50),
])
def test_known_indicator_values(closes, expected):
    rows = [{"date": f"day-{i}", "close": value} for i, value in enumerate(closes)]
    result = calculate_indicators(rows)
    assert result["sma_20"] == pytest.approx(sum(closes) / 20)
    assert result["sma_50"] is None
    assert result["rsi_14_simple"] == expected
    assert result["previous_bar_change_pct"] == pytest.approx((closes[-1] / closes[-2] - 1) * 100)


def test_short_history_does_not_invent_indicators():
    assert calculate_indicators([]) == {}
    result = calculate_indicators([{"date": "2026-08-01", "close": 10}])
    assert result["rsi_14_simple"] is None
    assert result["previous_bar_change_pct"] is None


def test_data_serialization_and_periods(ticker):
    data = YahooData("AAPL", ticker)
    assert data.prices()["data"][-1]["close"] == 165
    assert data.indicators()["data"]["sma_50"] == 140.5
    assert data.company()["data"]["currency"] == "USD"
    statements = data.financials()
    assert statements["income_statement"]["data"][0] == {
        "period_end": "2026-06-30", "values": {
            "TotalRevenue": 5000, "OperatingIncome": 800, "NetIncome": 600,
        },
    }
    assert data.news()["data"][0]["url"] == "https://example.com/earnings"
    assert data.news()["status"] == "ok"
    assert ticker.news_requests == 1
    assert clean({"value": math.nan}) == {"value": None}


def test_empty_data_differs_from_failed_fetch(ticker):
    ticker.get_news = lambda **kwargs: []
    data = YahooData("AAPL", ticker, news_search=lambda: [])
    assert data.news()["status"] == "empty"

    def offline(**kwargs):
        raise ConnectionError("Simulated failure")

    ticker.history = offline
    assert data.prices()["status"] == "unavailable"
    assert data.prices()["error"] == "ConnectionError"
    assert data.indicators()["status"] == "unavailable"
    assert data.indicators()["data"] is None


def test_financial_failure_keeps_other_statements(ticker):
    def unavailable(**kwargs):
        raise TimeoutError()

    ticker.get_balance_sheet = unavailable
    data = YahooData("AAPL", ticker)
    statements = data.financials()
    assert statements["income_statement"]["status"] == "ok"
    assert statements["balance_sheet"]["status"] == "unavailable"
    assert statements["cashflow"]["status"] == "ok"


def test_missing_financial_values_are_empty(ticker):
    ticker.get_income_stmt = lambda **kwargs: pd.DataFrame({pd.Timestamp("2026-06-30"): {
        "TotalRevenue": float("nan"),
    }})
    assert YahooData("AAPL", ticker).financials()["income_statement"]["status"] == "empty"


def test_flat_news_payload(ticker):
    ticker.get_news = lambda **kwargs: [{
        "title": "Flat article", "providerPublishTime": 1787918400,
        "publisher": "Example", "link": "https://example.com/flat",
    }]
    article = YahooData("AAPL", ticker).news()["data"][0]
    assert article["title"] == "Flat article"
    assert article["published_at"] is not None
    assert article["url"] == "https://example.com/flat"


def test_empty_news_feed_uses_ticker_tagged_search(ticker):
    ticker.get_news = lambda **kwargs: []
    data = YahooData("AAPL", ticker, news_search=lambda: [
        {"title": "Relevant result", "relatedTickers": ["AAPL"], "link": "https://example.com/a"},
        {"title": "Unrelated result", "relatedTickers": ["OTHER"]},
    ])
    assert [item["title"] for item in data.news()["data"]] == ["Relevant result"]
