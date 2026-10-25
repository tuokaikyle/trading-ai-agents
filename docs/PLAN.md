# Simplified Trading AI Agents: learning plan

## Implementation status

The workflow, CLI, yfinance tools, private analyst subgraphs, bounded debate,
validated decision, Markdown report, JSON trace, and learning walkthrough are
implemented. All 32 offline tests pass, including the real chat client's tool
protocol against a simulated endpoint. Live AAPL checks returned price history,
indicators, company metrics, quarterly statements, and eight news articles using
the yfinance search fallback.

The default configuration targets DeepSeek's OpenAI-compatible endpoint
(`deepseek-flash`); `LLM_MODEL` and `LLM_BASE_URL` select another provider or the
stronger `deepseek-v4-pro` without editing code. `LLM_THINKING` or
`LLM_REASONING_EFFORT` controls thinking mode. A complete live AAPL run with
`deepseek-flash` finished with a valid decision and saved both artifacts. The
implementation uses plain JSON with local schema validation and one repair attempt
for compatibility across endpoints.

## Goal and agreed choices

Build a small, readable application that teaches how LLM agents use tools, pass
state, debate, and produce a decision. Use Python 3.13 and uv at the repository
root. Keep `TradingAgents/` as a reference; run independently without importing it.

Your choices:

- **LangGraph**, following the original project's approach.
- **DeepSeek by default**, through an OpenAI-compatible API or local endpoint
  configured by environment variables. Start with one model for all roles.
- **Real data through yfinance only**, keeping the original's analyst categories
  while simplifying the data layer. Derive sentiment from Yahoo news.

`LLM_MODEL` and `LLM_BASE_URL` configure the endpoint before the first live run;
the defaults target DeepSeek. Verify that the chosen endpoint/model supports tool
calling early; OpenAI compatibility does not guarantee support for every optional
feature.

## Proposed workflow

```text
Ticker + current analysis date
              |
              v
   Market analyst <--> price/indicator tools
              |
              v
   Fundamentals analyst <--> financial-data tools
              |
              v
   News analyst <--> news tools
              |
              v
   Sentiment analyst <-- retrieved Yahoo news
              |
              v
     Bull researcher --> Bear researcher
              ^                |
              | optional repeat|
              +----------------+
                               |
                               v
                         Risk reviewer
                               |
                               v
                         Decision maker
                               |
                               v
                 BUY / HOLD / SELL + explanation
```

Use eight small roles. Keep the original's four analysts and bull/bear debate;
replace its three risk debaters with one reviewer, and combine its research
manager, trader, and portfolio manager into one final decision maker.

Run analysts sequentially initially so execution is easy to trace. Each analyst
gets a private message history and writes a separate report into shared state.
Later agents receive reports and relevant evidence. LangGraph controls handoffs;
the model chooses tool usage inside an analyst's bounded tool loop.

## Data scope

Use yfinance as the only external data package. Calculate technical indicators
locally and let the sentiment agent interpret the same news used by the news
analyst, with a different task: tone and uncertainty rather than event summary.
Their reports share evidence and must not be treated as independent confirmation.

| Data | yfinance interface | Simplified implementation |
| --- | --- | --- |
| Prices and volume | `Ticker.history()` | One price-history tool with a limited lookback |
| Technical indicators | Calculated from retrieved prices | Moving averages, RSI, and price change |
| Company overview | `Ticker.info` | A small selection of company metrics |
| Financial statements | `income_stmt`, `balance_sheet`, `cashflow` | Selected revenue, income, cash-flow, and balance-sheet facts |
| Company news | `Ticker.get_news()` | Capped headline/summary lists with dates and links when available |
| Sentiment | LLM analysis of retrieved news | News tone and uncertainty; no social-media sentiment claims |

Keep a thin yfinance wrapper that returns compact data to tools. Reuse fetched
news within a run. Omit SEC EDGAR, Reddit, StockTwits, FRED, Polymarket, and vendor
routing from this version. Inspect the original for useful details; preserve
required attribution/license notices if adapting code.

Start with current-date analysis of a US-listed stock. Record retrieval times,
actual market-data dates, and source coverage. Distinguish a source failure from
an empty result. Defer historical analysis and backtesting: current metrics and
live feeds must not be presented as past knowledge.

## Milestones

### 1. Setup and one LangGraph node

- Add LangGraph, LangChain's OpenAI-compatible integration, and minimal supporting
  dependencies through uv.
- Keep model and endpoint defaults in `trading_ai_agents/config.py`, with `LLM_API_KEY` required in
  `.env` and optional `LLM_MODEL` / `LLM_BASE_URL` overrides; provide an example
  file and ignore secrets and generated output.
- Create typed state and a `START -> model node -> END` graph.
- Check a normal response and tool-calling support with the configured model.

**Learn:** state, nodes, edges, messages, and graph invocation.
**Done when:** one documented uv command runs the node using the chosen endpoint.

### 2. Market analyst with tools

- Fetch real Yahoo price history and calculate a few indicators in Python.
- Expose functions as tools and bind them to the analyst model.
- Build an explicit analyst subgraph: `model -> tools -> model`, with a conditional
  edge that exits when the model returns its report. Avoid hiding this loop in a
  high-level agent factory.
- Start with three tool rounds, then force a tools-disabled report turn. Keep the
  graph recursion limit consistent with the bound.
- Print tool requests, arguments, results, and the report.

**Learn:** tool schemas, model-requested actions, tool messages, conditional edges,
and bounded loops.
**Done when:** a trace shows a real tool request/result/report cycle.

### 3. The remaining analyst reports

- Add fundamentals, news, and sentiment using the sources above.
- Reuse one small analyst-subgraph builder for tool-using analysts.
- Give the sentiment agent the already retrieved news without a separate tool
  loop. Explain that it measures news sentiment, not social-media sentiment.
- Give each role a short prompt and private message history.
- Store reports, evidence, dates, and missing-data notes in explicit `TypedDict`
  state fields.

**Learn:** role specialization, isolated conversations, subgraphs, and shared state.
**Done when:** four reports contain identifiable evidence or clear limitations.

### 4. Bull and bear debate

- Add bull and bear nodes that read all four reports.
- Start with one bull turn followed by one bear response addressing that argument.
- Add a conditional edge for an optional second round. One round means one turn
  from each researcher; store the transcript and count explicitly.
- Require arguments to distinguish evidence from assumptions.

**Learn:** handoffs, conversation history, and conditional graph cycles.
**Done when:** the debate responds to earlier messages and exits at its limit.

### 5. Risk review and final decision

- Add one risk reviewer after the debate to assess uncertainty and weak evidence.
- Give the decision maker the reports, debate, risk review, and source limitations.
- Validate a small schema: `action` (`BUY`, `HOLD`, or `SELL`), `rationale`,
  `supporting_evidence`, and `risks`.
- Use structured output supported by the endpoint. If native schema output is
  unavailable, request JSON and validate locally, with at most one repair attempt.
- Keep recommendations qualitative; omit brokerage execution and position sizing.

**Learn:** review stages, structured output, and model-response validation.
**Done when:** the graph ends in a valid decision supported by saved inputs.

### 6. CLI, traces, and documentation

- Provide `uv run main.py --ticker AAPL` and optional `--debate-rounds 2`.
- Stream node progress; save a Markdown report and JSON trace per run.
- Record agent instructions, supplied messages, tool requests/results, and model
  outputs, excluding credentials. Do not request hidden chain-of-thought.
- Add a graph diagram, a complete walkthrough, and a mapping to the original.
- Explain where to edit a prompt, tool, state field, node, or edge.

**Learn:** inspect a complete run, then change one component yourself.
**Done when:** the README explains a run and its generated artifacts.

## Suggested file layout

Keep one small package so runtime code is separate from project metadata.
Split modules further only when it helps reading.

```text
main.py                         # thin CLI entry
trading_ai_agents/
  cli.py                        # arguments, progress, report and trace output
  config.py                     # environment settings and model construction
  state.py                      # graph state and decision schema
  data.py                       # yfinance wrapper and compact formatting
  tools.py                      # model-facing tools and calculations
  agents.py                     # short role prompts and node functions
  graph.py                      # analyst subgraphs, workflow edges, routing
  observability.py              # message records and Recorder
  reporting.py                  # Markdown and JSON artifacts
  __main__.py                   # python -m trading_ai_agents
  __init__.py
tests/                          # focused tests with scripted inputs
docs/PLAN.md                    # this plan
README.md, LICENSE, NOTICE      # project metadata
```

Expected dependencies: `langgraph`, `langchain-core`, `langchain-openai`,
`pydantic`, `python-dotenv`, and `yfinance`; `pytest` for tests.
Use the standard library CLI and Markdown output initially.

## Verification and boundaries

- Test numeric tools against known values.
- Use scripted model responses and stubbed sources to check tool messages, private
  histories, report handoffs, loop limits, missing data, and invalid output without
  paid API calls.
- Run one live end-to-end example after endpoint credentials are configured.
- Default to one ticker, one model, sequential analysts, and one debate round.
- Defer databases, persistent memory, checkpoint resume, portfolio accounting,
  backtesting, multiple providers, web UI, and extensive recovery machinery.

Success means you can explain each model call, inspect what each agent sees, and
change a prompt or tool to observe its effect. Trading profitability is outside
this learning plan.

## Framework references

- [LangGraph workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [ChatOpenAI integration and endpoint configuration](https://docs.langchain.com/oss/python/integrations/chat/openai)
- [yfinance Ticker data interfaces](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.html)
