# Contributing

Thanks for considering a contribution. This project is small on purpose: it is a
readable teaching example, so clarity matters more than features.

## Getting set up

```bash
uv python install 3.13
uv sync
uv run pytest -q
```

Tests are fully offline and run in about a second. They use fixed price data and
scripted model responses, so **no API key and no network access are required**. Do
not add a test that calls a real model or Yahoo Finance.

To try the application itself you need an OpenAI-compatible endpoint:

```bash
cp .env.example .env   # then set LLM_API_KEY
uv run main.py --ticker AAPL
```

Never commit `.env` or a real key. If you think a key leaked, see [SECURITY.md](SECURITY.md).

## Pull requests

- Keep the change focused; one topic per pull request.
- Add or update a test for behaviour changes. If a change is documentation-only, say so.
- Run `uv run pytest -q` before pushing; CI runs the same command.
- Match the surrounding style. The codebase uses short modules, docstrings that
  explain *why*, and no unnecessary dependencies.

If you add a dependency, add it with `uv add <package>` (or `uv add --dev`) so
`pyproject.toml` and `uv.lock` stay in sync, and explain in the pull request why the
standard library is not enough.

## Good first contributions

- Add an indicator in `trading_ai_agents/data.py` and expose it through a tool.
- Add a role prompt variant and compare the resulting reports.
- Improve error messages when an endpoint does not support tool calling.

## Scope and conduct

This project is for research and education. It does not place orders and does not
give financial advice. Contributions that present generated output as investment
advice, or that add live trading, are out of scope.

By participating you agree to follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
