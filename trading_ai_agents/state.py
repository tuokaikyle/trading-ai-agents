"""The values passed between graph nodes, plus the final output contract."""

from typing import Literal, TypedDict

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class Decision(BaseModel):
    action: Literal["BUY", "HOLD", "SELL"]
    rationale: str = Field(min_length=1)
    supporting_evidence: list[str] = Field(min_length=1)
    risks: list[str] = Field(min_length=1)


class AnalystState(TypedDict):
    # This state is private to one analyst subgraph. Nodes replace the list
    # explicitly, so there is no message reducer or hidden accumulation.
    messages: list[BaseMessage]
    tool_rounds: int
    report: str


class WorkflowState(TypedDict):
    ticker: str
    analysis_time: str
    market_report: str
    fundamentals_report: str
    news_report: str
    sentiment_report: str
    evidence: dict
    debate: list[dict[str, str]]
    debate_round: int
    risk_report: str
    decision: dict


def initial_state(ticker: str, analysis_time: str) -> WorkflowState:
    return {
        "ticker": ticker,
        "analysis_time": analysis_time,
        "market_report": "",
        "fundamentals_report": "",
        "news_report": "",
        "sentiment_report": "",
        "evidence": {},
        "debate": [],
        "debate_round": 0,
        "risk_report": "",
        "decision": {},
    }
