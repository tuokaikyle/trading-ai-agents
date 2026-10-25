"""Model settings: env vars with DeepSeek-compatible defaults.

The defaults target DeepSeek's OpenAI-compatible Chat Completions API, so a
DeepSeek key works without editing this file. Point ``LLM_MODEL`` and
``LLM_BASE_URL`` at another OpenAI-compatible provider to switch models.
``LLM_THINKING`` or ``LLM_REASONING_EFFORT`` controls DeepSeek thinking mode.
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


# Defaults are overridable through LLM_MODEL and LLM_BASE_URL. Keep the API key
# out of this file; it belongs in .env (or the process environment for CI).
# DeepSeek currently documents deepseek-flash and deepseek-v4-pro as model IDs.
DEFAULT_MODEL = "deepseek-flash"
DEFAULT_BASE_URL = "https://api.deepseek.com"

THINKING_VALUES = ("enabled", "disabled")
# DeepSeek maps minimal -> low and medium/xhigh -> high for compatibility.
REASONING_EFFORT_VALUES = ("none", "low", "high", "max", "minimal", "medium", "xhigh")


@dataclass
class Settings:
    model: str
    base_url: str
    api_key: str = field(repr=False)
    thinking: str | None = None
    reasoning_effort: str | None = None

    @classmethod
    def from_env(cls):
        load_dotenv()
        api_key = os.getenv("LLM_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "Set LLM_API_KEY in .env. The default provider is DeepSeek; "
                "set LLM_MODEL and LLM_BASE_URL for another OpenAI-compatible API."
            )
        model = os.getenv("LLM_MODEL", "").strip() or DEFAULT_MODEL
        base_url = os.getenv("LLM_BASE_URL", "").strip() or DEFAULT_BASE_URL
        base_url = base_url.rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("LLM_BASE_URL must start with http:// or https://.")

        thinking = os.getenv("LLM_THINKING", "").strip().lower() or None
        if thinking and thinking not in THINKING_VALUES:
            raise ValueError(
                f"LLM_THINKING must be one of: {', '.join(THINKING_VALUES)}."
            )
        reasoning_effort = os.getenv("LLM_REASONING_EFFORT", "").strip().lower() or None
        if reasoning_effort and reasoning_effort not in REASONING_EFFORT_VALUES:
            raise ValueError(
                "LLM_REASONING_EFFORT must be one of: "
                f"{', '.join(REASONING_EFFORT_VALUES)}."
            )
        if thinking and reasoning_effort:
            raise ValueError(
                "Set either LLM_THINKING or LLM_REASONING_EFFORT, not both; "
                "reasoning_effort already controls thinking mode."
            )
        return cls(model, base_url, api_key, thinking, reasoning_effort)

    def create_model(self):
        request_options = {}
        if self.thinking:
            # ChatOpenAI has no `thinking` field; extra_body adds it to the JSON.
            request_options["extra_body"] = {"thinking": {"type": self.thinking}}
        if self.reasoning_effort:
            request_options["reasoning_effort"] = self.reasoning_effort
        return ChatOpenAI(
            model=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
            use_responses_api=False,
            timeout=90,
            max_retries=1,
            **request_options,
        )
