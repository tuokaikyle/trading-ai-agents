import json

import pandas as pd
import pytest
from langchain_core.messages import AIMessage, ToolMessage


class ExampleTicker:
    """Known observations for tests only; application runs always use yfinance."""

    def __init__(self):
        self.news_requests = 0

    def history(self, **kwargs):
        return pd.DataFrame({
            "Open": range(100, 165), "High": range(102, 167),
            "Low": range(99, 164), "Close": range(101, 166), "Volume": [1000] * 65,
        }, index=pd.date_range("2026-06-01", periods=65, freq="B"))

    @property
    def info(self):
        return {"shortName": "Example Company", "currency": "USD",
                "financialCurrency": "USD", "marketCap": 1000000, "trailingPE": 20}

    def get_income_stmt(self, **kwargs):
        return pd.DataFrame({pd.Timestamp("2026-06-30"): {
            "TotalRevenue": 5000, "OperatingIncome": 800, "NetIncome": 600,
        }})

    def get_balance_sheet(self, **kwargs):
        return pd.DataFrame({pd.Timestamp("2026-06-30"): {
            "TotalAssets": 10000, "TotalDebt": 2000,
        }})

    def get_cashflow(self, **kwargs):
        return pd.DataFrame({pd.Timestamp("2026-06-30"): {
            "OperatingCashFlow": 900, "FreeCashFlow": 500,
        }})

    def get_news(self, **kwargs):
        self.news_requests += 1
        return [{"content": {
            "title": "Example company reports higher revenue", "summary": "Revenue rose.",
            "pubDate": "2026-08-28T12:00:00Z", "provider": {"displayName": "Example"},
            "canonicalUrl": {"url": "https://example.com/earnings"},
        }}]


VALID_DECISION = {
    "action": "HOLD", "rationale": "The example evidence is limited.",
    "supporting_evidence": ["Positive price trend in the supplied bars."],
    "risks": ["News coverage is a small sample."],
}


class ScriptedModel:
    """Select responses by role so graph ordering and context can be asserted."""

    def __init__(self):
        self.calls = []
        self.decision_responses = [json.dumps(VALID_DECISION)]

    def bind_tools(self, tools):
        parent = self

        class Bound:
            def invoke(self, messages):
                parent.calls.append((True, list(messages)))
                if not any(isinstance(message, ToolMessage) for message in messages):
                    return AIMessage(content="", tool_calls=[
                        {"name": tool.name, "args": {}, "id": f"call-{tool.name}"}
                        for tool in tools
                    ])
                role = messages[0].content.splitlines()[0]
                return AIMessage(content=f"{role} report based on supplied tools.")
        return Bound()

    def invoke(self, messages):
        self.calls.append((False, list(messages)))
        instruction = messages[0].content
        if instruction.startswith("You are the decision maker."):
            return AIMessage(content=self.decision_responses.pop(0))
        if instruction.startswith("You are the bull."):
            return AIMessage(content="Bull argument: the supplied trend is positive.")
        if instruction.startswith("You are the bear."):
            return AIMessage(content="Bear response: the bull's trend evidence is limited.")
        return AIMessage(content="Report: supplied evidence has important limitations.")


@pytest.fixture
def ticker():
    return ExampleTicker()


@pytest.fixture
def model():
    return ScriptedModel()
