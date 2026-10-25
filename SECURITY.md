# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for a security problem. Use GitHub's private
vulnerability reporting on the repository's **Security** tab, or contact the
maintainer directly. Include the affected version or commit, reproduction steps, and
the impact you believe it has. Expect an initial reply within about a week.

## Supported versions

This is a pre-1.0 educational project. Security fixes land on `main` only; there are
no maintained release branches.

## Threat model

Worth knowing before you deploy this anywhere public:

- **Prompt injection via retrieved data.** News headlines, summaries, and company
  metadata are attacker-influenced text that is fed into model prompts. The prompts
  instruct the model to treat retrieved text as evidence and never as instructions,
  but that is a mitigation, not a guarantee. Do not give these agents access to
  anything sensitive or irreversible.
- **The agents have no write access.** Tools in `trading_ai_agents/tools.py` only read
  from Yahoo Finance. The ticker is fixed by the CLI and is validated, so the model
  cannot change it or reach other hosts. Treat the model as an untrusted input
  source, not a trusted operator.
- **API keys.** The key is read from `LLM_API_KEY` in `.env` or the environment. It is
  excluded from `repr`, and run traces record only a whitelisted subset of settings,
  so the key is not written to `runs/`. Failure messages avoid printing raw SDK
  errors because those can embed authenticated URLs. If you add logging or a new
  serializer, keep it that way.
- **Generated artifacts contain full prompts and tool output.** `runs/*/trace.json`
  includes fetched news text and every model message. Review a trace before sharing
  it; `runs/` is gitignored for this reason.
- **Output is not advice.** Reports are generated text validated only for JSON shape.
  Validation checks format, not correctness.

## If a key leaks

Rotate it at the provider immediately; assume any committed or shared key is burned.
Then remove it from the repository history (for example with `git filter-repo`) rather
than only deleting it in a new commit.
