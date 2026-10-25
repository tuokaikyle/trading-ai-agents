"""Read this file to follow every handoff and loop in the application."""

import json

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from .agents import (
    ANALYST_PROMPTS, GROUNDING, decision_node, researcher_node, risk_node, sentiment_node,
)
from .observability import message_text
from .state import AnalystState, WorkflowState
from .tools import build_tools


def build_analyst(model, tools, role, recorder, max_tool_rounds=3):
    """One private model/tools loop, reused for the three tool-using analysts."""
    with_tools = model.bind_tools(tools)
    allowed_tools = {tool.name: tool for tool in tools}

    def model_turn(state):
        response = recorder.invoke(with_tools, role, state["messages"])
        if not response.tool_calls:
            if not any(isinstance(m, ToolMessage) for m in state["messages"]):
                raise RuntimeError(
                    f"{role}: model returned no tool calls. Check that your model/endpoint "
                    "supports tools and follows the analyst instructions."
                )
            if not message_text(response):
                raise RuntimeError(f"{role}: empty analyst report.")
        return {"messages": [*state["messages"], response],
                "report": "" if response.tool_calls else message_text(response)}

    def tool_turn(state):
        results = []
        for call in state["messages"][-1].tool_calls:
            try:
                if call["name"] not in allowed_tools:
                    raise ValueError("Unknown tool")
                result = allowed_tools[call["name"]].invoke(call["args"])
            except Exception as exc:
                result = {"status": "tool_error", "error": type(exc).__name__,
                          "hint": "Use an available tool with its documented arguments."}
            recorder.tool(role, call, result)
            results.append(ToolMessage(
                content=json.dumps(result, ensure_ascii=False, allow_nan=False),
                tool_call_id=call["id"], name=call["name"],
            ))
        return {"messages": [*state["messages"], *results],
                "tool_rounds": state["tool_rounds"] + 1}

    def finish(state):
        messages = [*state["messages"], HumanMessage(content=
            "Your tool-round budget is exhausted. Write your final report now using "
            "the evidence collected. Clearly state any missing data. Do not call tools.")]
        response = recorder.invoke(model, role, messages)  # Unbound model: tools disabled.
        if response.tool_calls or not message_text(response):
            raise RuntimeError(f"{role}: model did not produce a report at the tool limit.")
        return {"messages": [*messages, response], "report": message_text(response)}

    graph = StateGraph(AnalystState)
    graph.add_node("model", model_turn)
    graph.add_node("tools", tool_turn)
    graph.add_node("finish", finish)
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", lambda s:
                                "tools" if s["messages"][-1].tool_calls else END,
                                ["tools", END])
    graph.add_conditional_edges("tools", lambda s:
                                "finish" if s["tool_rounds"] >= max_tool_rounds else "model",
                                ["finish", "model"])
    graph.add_edge("finish", END)
    return graph.compile()


def build_workflow(model, data, recorder, debate_rounds=1, max_tool_rounds=3):
    if not 1 <= debate_rounds <= 3 or not 1 <= max_tool_rounds <= 5:
        raise ValueError("Use 1-3 debate rounds and 1-5 tool rounds.")
    graph = StateGraph(WorkflowState)

    def analyst_node(role, tools):
        private_graph = build_analyst(model, tools, role, recorder, max_tool_rounds)

        def run(state):
            result = private_graph.invoke({
                "messages": [
                    SystemMessage(content=f"You are the {role} analyst.\n{GROUNDING}\n"
                                  + ANALYST_PROMPTS[role]),
                    HumanMessage(content=f"Analyze {state['ticker']}. Current run time: "
                                 f"{state['analysis_time']}. Use the supplied tools."),
                ],
                "tool_rounds": 0, "report": "",
            }, {"recursion_limit": 2 * max_tool_rounds + 5})
            recorder.report(role, result["report"])
            return {f"{role}_report": result["report"], "evidence": dict(data.evidence)}
        return run

    for role, tools in build_tools(data).items():
        graph.add_node(role, analyst_node(role, tools))
    graph.add_node("sentiment", sentiment_node(model, data, recorder))
    graph.add_node("bull", researcher_node(model, recorder, "bull"))
    graph.add_node("bear", researcher_node(model, recorder, "bear"))
    graph.add_node("risk", risk_node(model, recorder))
    graph.add_node("decision", decision_node(model, recorder))

    sequence = [START, "market", "fundamentals", "news", "sentiment", "bull", "bear"]
    for before, after in zip(sequence, sequence[1:]):
        graph.add_edge(before, after)
    graph.add_conditional_edges("bear", lambda s:
                                "bull" if s["debate_round"] < debate_rounds else "risk",
                                ["bull", "risk"])
    graph.add_edge("risk", "decision")
    graph.add_edge("decision", END)
    return graph.compile()
