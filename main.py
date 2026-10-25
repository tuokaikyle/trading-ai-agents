"""Thin entry point: ``uv run main.py --ticker AAPL``.

The implementation lives in the ``trading_ai_agents`` package. ``python -m
trading_ai_agents`` is the equivalent package entry point.
"""

from trading_ai_agents.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
