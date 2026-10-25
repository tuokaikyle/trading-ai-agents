"""Plain Markdown and JSON artifacts, with no reporting framework."""

import json


def write_run(directory, state, events, settings):
    directory.mkdir(parents=True, exist_ok=True)
    trace = {"status": "completed", "settings": settings, "state": state, "events": events}
    (directory / "trace.json").write_text(
        json.dumps(trace, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8",
    )
    decision = state["decision"]
    lines = [
        f"# {state['ticker']}: {decision['action']}", "",
        f"Analysis started: {state['analysis_time']}", "",
        "Educational current-data analysis. No orders are placed.", "",
        "## Decision", "", decision["rationale"], "",
        "### Supporting evidence", "",
        *[f"- {item}" for item in decision["supporting_evidence"]], "",
        "### Risks", "", *[f"- {item}" for item in decision["risks"]], "",
    ]
    for role in ("market", "fundamentals", "news", "sentiment"):
        lines += [f"## {role.title()} analyst", "", state[f"{role}_report"], ""]
    lines += ["## Debate", ""]
    for turn in state["debate"]:
        lines += [f"### {turn['speaker'].title()}", "", turn["argument"], ""]
    lines += ["## Risk review", "", state["risk_report"], "", "## Data coverage", ""]
    for name, record in state["evidence"].items():
        lines += [f"- **{name}**: {record['status']}; retrieved {record['retrieved_at']}. "
                  f"{record['note']}"]
    lines += ["", "Full source data, prompts, messages, and tool results are in `trace.json`.", ""]
    (directory / "report.md").write_text("\n".join(lines), encoding="utf-8")
