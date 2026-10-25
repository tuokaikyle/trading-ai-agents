# Changelog

Notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Until 1.0.0, minor
versions may include breaking changes.

## [Unreleased]

## [0.1.0] - 2026-10-25

First public release.

### Added

- LangGraph workflow with four analysts (market, fundamentals, news, sentiment), a
  bull/bear debate, a risk review, and a validated final decision.
- Bounded tool loops per analyst: private message history, a configurable tool-round
  budget, and a final tools-disabled call so a run always ends with a report.
- yfinance data layer with per-run caching, retrieval timestamps, and explicit `ok`,
  `empty`, or `unavailable` status on every source record.
- Locally computed indicators (price change, 20/50-bar moving averages, simple
  RSI-14) with nulls for insufficient history.
- `report.md` and `trace.json` artifacts per run, with API keys and endpoint URLs
  excluded from traces.
- OpenAI-compatible model configuration through `LLM_API_KEY`, `LLM_MODEL`, and
  `LLM_BASE_URL`, defaulting to DeepSeek.
- Thinking-mode controls through `LLM_THINKING` or `LLM_REASONING_EFFORT`.
- CLI with `--ticker`, `--debate-rounds`, `--tool-rounds`, `--output-dir`,
  `--verbose`, and a credential-free `--draw-graph`.
- 32 offline tests covering the full graph, private histories, tool limits, debate
  rounds, source failures, decision repair, saved artifacts, and the chat client's
  tool protocol against a simulated HTTP endpoint.

[Unreleased]: https://github.com/tuokaikyle/trading-ai-agents/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tuokaikyle/trading-ai-agents/releases/tag/v0.1.0
