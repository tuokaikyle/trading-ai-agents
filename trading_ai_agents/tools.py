"""The model's allowed actions. The ticker is fixed by the CLI, not the LLM."""

from langchain_core.tools import tool

from .data import YahooData


def build_tools(data: YahooData) -> dict:
    @tool
    def get_prices() -> dict:
        """Get the latest 30 adjusted daily OHLCV bars for the selected stock."""
        record = data.prices()
        if record["status"] == "ok":
            return {**record, "data": record["data"][-30:]}
        return record

    @tool
    def get_indicators() -> dict:
        """Get price change, 20/50-day moving averages, and simple 14-day RSI."""
        return data.indicators()

    @tool
    def get_company_info() -> dict:
        """Get current company description, currency, valuation, and financial metrics."""
        return data.company()

    @tool
    def get_financial_statements() -> dict:
        """Get selected values from the latest two available quarterly statements."""
        return data.financials()

    @tool
    def get_news() -> dict:
        """Get a small recent company news sample with summaries, dates, and links."""
        return data.news()

    return {
        "market": [get_prices, get_indicators],
        "fundamentals": [get_company_info, get_financial_statements],
        "news": [get_news],
    }
