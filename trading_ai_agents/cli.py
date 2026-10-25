"""Run a current stock analysis, or draw the graph without credentials."""

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from .config import Settings
from .data import YahooData
from .graph import build_workflow
from .observability import Recorder
from .reporting import write_run
from .state import initial_state


def ticker_symbol(value):
    value = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9^][A-Z0-9.^=-]{0,19}", value):
        raise argparse.ArgumentTypeError("Use a stock ticker such as AAPL or BRK-B.")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", type=ticker_symbol, help="Yahoo ticker, e.g. AAPL")
    parser.add_argument("--debate-rounds", type=int, choices=range(1, 4), default=1)
    parser.add_argument("--tool-rounds", type=int, choices=range(1, 6), default=3)
    parser.add_argument("--output-dir", type=Path, default=Path("runs"))
    parser.add_argument("--verbose", action="store_true", help="Print reports and full tool results")
    parser.add_argument("--draw-graph", action="store_true", help="Print Mermaid; no API calls")
    args = parser.parse_args(argv)
    if not args.ticker and not args.draw_graph:
        parser.error("--ticker is required unless --draw-graph is used")

    recorder = Recorder(verbose=args.verbose)
    if args.draw_graph:
        # Construction only needs bind_tools; no model or data requests are made.
        class DiagramModel:
            def bind_tools(self, tools):
                return self

        graph = build_workflow(DiagramModel(), YahooData("AAPL"), recorder)
        print(graph.get_graph().draw_mermaid())
        return 0

    try:
        settings = Settings.from_env()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    now = datetime.now(UTC)
    # Microseconds avoid overwriting a previous run; symbols cannot contain paths.
    run_dir = args.output_dir / f"{now:%Y%m%dT%H%M%S%fZ}-{args.ticker}"
    try:
        run_dir.mkdir(parents=True)
        print(f"Analyzing {args.ticker} with {settings.model}; current data only.")
        data = YahooData(args.ticker)
        graph = build_workflow(
            settings.create_model(), data, recorder, args.debate_rounds, args.tool_rounds,
        )
        result = graph.invoke(initial_state(args.ticker, now.isoformat()), {
            "recursion_limit": 20 + 2 * args.debate_rounds,
        })
        write_run(run_dir, result, recorder.events, {
            "model": settings.model, "debate_rounds": args.debate_rounds,
            "max_tool_rounds": args.tool_rounds,
        })
        print("\n" + json.dumps(result["decision"], indent=2, ensure_ascii=False))
        print(f"\nReport: {run_dir.resolve() / 'report.md'}")
        print(f"Trace:  {run_dir.resolve() / 'trace.json'}")
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        # Preserve completed actions even when a provider rejects a request.
        # Do not print arbitrary SDK errors that may contain authenticated URLs.
        error = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        print(f"Run stopped: {error}", file=sys.stderr)
        if run_dir.is_dir():
            failure = {"status": "failed", "error": error, "events": recorder.events}
            (run_dir / "trace.json").write_text(
                json.dumps(failure, indent=2, ensure_ascii=False), encoding="utf-8",
            )
            print(f"Partial trace: {run_dir.resolve() / 'trace.json'}", file=sys.stderr)
        return 1
