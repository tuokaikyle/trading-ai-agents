import json

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from conftest import VALID_DECISION
from trading_ai_agents.data import YahooData
from trading_ai_agents.graph import build_analyst, build_workflow
from trading_ai_agents.cli import main
from trading_ai_agents.observability import Recorder
from trading_ai_agents.reporting import write_run
from trading_ai_agents.state import initial_state


def recorder():
    return Recorder(emit=lambda _: None)


@pytest.mark.parametrize("rounds", [1, 2])
def test_full_graph_and_private_histories(ticker, model, tmp_path, rounds):
    data = YahooData("AAPL", ticker)
    trace = recorder()
    result = build_workflow(model, data, trace, debate_rounds=rounds).invoke(
        initial_state("AAPL", "2026-08-29T00:00:00+00:00")
    )
    assert result["decision"] == VALID_DECISION
    assert result["debate_round"] == rounds
    assert [turn["speaker"] for turn in result["debate"]] == ["bull", "bear"] * rounds
    assert ticker.news_requests == 1  # News + sentiment share one observation.

    # Every analyst starts clean, rather than inheriting a previous conversation.
    first_turns = [messages for bound, messages in model.calls
                   if bound and not any(isinstance(m, ToolMessage) for m in messages)]
    assert len(first_turns) == 3
    assert all(len(messages) == 2 for messages in first_turns)
    bear_inputs = [messages[1].content for _, messages in model.calls
                   if messages[0].content.startswith("You are the bear.")]
    assert all("Bull argument:" in content for content in bear_inputs)
    decision_input = model.calls[-1][1][1].content
    assert "risk" in decision_input.lower()
    assert "Bear response:" in decision_input
    assert all(result[f"{role}_report"] for role in ("market", "fundamentals", "news", "sentiment"))

    write_run(tmp_path, result, trace.events, {"model": "scripted"})
    saved = json.loads((tmp_path / "trace.json").read_text())
    assert saved["status"] == "completed"
    assert any(event["kind"] == "tool" for event in saved["events"])
    assert "## Risk review" in (tmp_path / "report.md").read_text()


def test_invalid_decision_repaired_once(ticker, model):
    model.decision_responses = ['{"action": "MAYBE"}', json.dumps(VALID_DECISION)]
    trace = recorder()
    result = build_workflow(model, YahooData("AAPL", ticker), trace).invoke(
        initial_state("AAPL", "now")
    )
    assert result["decision"]["action"] == "HOLD"
    calls = [event for event in trace.events
             if event["kind"] == "model_input" and event["agent"] == "decision"]
    assert len(calls) == 2
    assert "did not match" in calls[-1]["messages"][-1]["content"]


def test_invalid_decision_stops_after_repair(ticker, model):
    model.decision_responses = ["invalid", "still invalid"]
    with pytest.raises(RuntimeError, match="one JSON repair"):
        build_workflow(model, YahooData("AAPL", ticker), recorder()).invoke(
            initial_state("AAPL", "now")
        )


def test_tool_loop_is_bounded_and_final_turn_disables_tools():
    calls = []

    @tool
    def sample() -> str:
        """Return one known observation."""
        calls.append(True)
        return "observed"

    class RepeatingModel:
        def bind_tools(self, tools):
            class Bound:
                def invoke(self, messages):
                    return AIMessage(content="", tool_calls=[
                        {"name": "sample", "args": {}, "id": f"call-{len(messages)}"}
                    ])
            return Bound()

        def invoke(self, messages):
            assert "budget is exhausted" in messages[-1].content
            return AIMessage(content="Final report from the collected evidence.")

    result = build_analyst(RepeatingModel(), [sample], "test", recorder(), 2).invoke({
        "messages": [HumanMessage(content="Analyze")], "tool_rounds": 0, "report": "",
    })
    assert len(calls) == 2
    assert result["tool_rounds"] == 2
    assert result["report"].startswith("Final report")


def test_unknown_tool_is_not_executed():
    class BadToolModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            if isinstance(messages[-1], ToolMessage):
                assert json.loads(messages[-1].content)["status"] == "tool_error"
                return AIMessage(content="Unable to collect requested evidence.")
            return AIMessage(content="", tool_calls=[
                {"name": "run_shell", "args": {"command": "unused"}, "id": "bad"}
            ])

    result = build_analyst(BadToolModel(), [], "test", recorder()).invoke({
        "messages": [HumanMessage(content="Analyze")], "tool_rounds": 0, "report": "",
    })
    assert result["report"] == "Unable to collect requested evidence."


def test_no_tool_support_fails_clearly():
    class NoTools:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            return AIMessage(content="An unsupported guess.")

    with pytest.raises(RuntimeError, match="no tool calls"):
        build_analyst(NoTools(), [], "market", recorder()).invoke({
            "messages": [HumanMessage(content="Analyze")], "tool_rounds": 0, "report": "",
        })


def test_real_chat_client_tool_protocol_without_network():
    requests = []

    @tool
    def observation() -> dict:
        """Return a known observation."""
        return {"close": 123}

    def endpoint(request):
        body = json.loads(request.content)
        requests.append(body)
        if body["messages"][-1]["role"] == "tool":
            assert json.loads(body["messages"][-1]["content"]) == {"close": 123}
            message = {"role": "assistant", "content": "The observed close was 123."}
            finish = "stop"
        else:
            assert body["tools"][0]["function"]["name"] == "observation"
            message = {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call-1", "type": "function",
                "function": {"name": "observation", "arguments": "{}"},
            }]}
            finish = "tool_calls"
        return httpx.Response(200, json={
            "id": "test", "object": "chat.completion", "created": 1, "model": "test",
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        })

    with httpx.Client(transport=httpx.MockTransport(endpoint)) as client:
        model = ChatOpenAI(model="test", base_url="http://example.test/v1",
                           api_key="test-only", http_client=client, use_responses_api=False)
        result = build_analyst(model, [observation], "market", recorder()).invoke({
            "messages": [SystemMessage(content="Use observation."), HumanMessage(content="Analyze")],
            "tool_rounds": 0, "report": "",
        })
    assert result["report"] == "The observed close was 123."
    assert len(requests) == 2


def test_graph_diagram_needs_no_credentials(capsys):
    assert main(["--draw-graph"]) == 0
    assert "fundamentals" in capsys.readouterr().out


def test_cli_missing_configuration(monkeypatch, capsys):
    monkeypatch.setattr("trading_ai_agents.config.load_dotenv", lambda: None)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert main(["--ticker", "AAPL"]) == 2
    assert "Configuration error" in capsys.readouterr().err


def test_cli_writes_complete_artifacts(monkeypatch, ticker, model, tmp_path):
    class TestSettings:
        model = "scripted"

        def create_model(self):
            return model

    monkeypatch.setattr("trading_ai_agents.cli.Settings.from_env", lambda: TestSettings())
    monkeypatch.setattr("trading_ai_agents.cli.YahooData", lambda symbol: YahooData(symbol, ticker))
    assert main(["--ticker", "aapl", "--output-dir", str(tmp_path)]) == 0
    trace_file = next(tmp_path.glob("*-AAPL/trace.json"))
    assert json.loads(trace_file.read_text())["state"]["decision"] == VALID_DECISION
    assert trace_file.with_name("report.md").exists()


def test_cli_keeps_partial_trace_on_provider_failure(monkeypatch, ticker, tmp_path, capsys):
    class FailingModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            raise ConnectionError("Simulated provider failure")

    class TestSettings:
        model = "scripted"

        def create_model(self):
            return FailingModel()

    monkeypatch.setattr("trading_ai_agents.cli.Settings.from_env", lambda: TestSettings())
    monkeypatch.setattr("trading_ai_agents.cli.YahooData", lambda symbol: YahooData(symbol, ticker))
    assert main(["--ticker", "AAPL", "--output-dir", str(tmp_path)]) == 1
    trace = json.loads(next(tmp_path.glob("*-AAPL/trace.json")).read_text())
    assert trace["status"] == "failed"
    assert any(event["kind"] == "model_error" for event in trace["events"])
    assert "model request failed" in capsys.readouterr().err
