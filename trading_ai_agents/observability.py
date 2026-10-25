"""Observable messages and tool actions, rather than hidden reasoning."""

import json
from datetime import UTC, datetime

from langchain_core.messages import AIMessage


def message_text(message) -> str:
    if isinstance(message.content, str):
        return message.content.strip()
    # Some compatible endpoints return typed content blocks.
    return "\n".join(
        block.get("text", "") for block in message.content
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()


def message_record(message):
    record = {"role": message.type, "content": message_text(message)}
    if getattr(message, "tool_calls", None):
        record["tool_calls"] = message.tool_calls
    if getattr(message, "tool_call_id", None):
        record["tool_call_id"] = message.tool_call_id
    return record


class Recorder:
    def __init__(self, verbose=False, emit=print):
        self.events = []
        self.verbose = verbose
        self.emit = emit

    def add(self, kind, agent, **payload):
        self.events.append({
            "time": datetime.now(UTC).isoformat(), "kind": kind,
            "agent": agent, **payload,
        })

    def invoke(self, model, agent, messages):
        self.emit(f"[{agent}] model call")
        self.add("model_input", agent, messages=[message_record(m) for m in messages])
        try:
            response = model.invoke(messages)
        except Exception as exc:
            self.add("model_error", agent, error=type(exc).__name__)
            raise RuntimeError(
                f"{agent}: model request failed ({type(exc).__name__}). "
                "Check endpoint, model, credentials, and tool-calling support."
            ) from exc
        if not isinstance(response, AIMessage) or response.invalid_tool_calls:
            raise RuntimeError(f"{agent}: endpoint returned an invalid chat/tool response.")
        self.add("model_output", agent, message=message_record(response))
        if self.verbose:
            self.emit(json.dumps(message_record(response), ensure_ascii=False, default=str))
        return response

    def tool(self, agent, call, result):
        self.add("tool", agent, call=call, result=result)
        rendered = json.dumps(result, ensure_ascii=False, default=str)
        self.emit(f"[{agent}] tool {call['name']}({json.dumps(call['args'])})")
        self.emit(rendered if self.verbose else rendered[:240])

    def report(self, agent, report):
        self.add("report", agent, report=report)
        self.emit(f"[{agent}] report ready")
        if self.verbose:
            self.emit(report)
