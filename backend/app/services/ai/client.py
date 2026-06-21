"""The single Anthropic SDK touch-point for the AI assistant.

Everything else in :mod:`app.services.ai` depends on this module's *interface*,
not on ``anthropic`` directly. That keeps the skills unit-testable without a live
API (tests inject a fake client) and makes the whole module extractable into a
separate service later by swapping this file alone.

Design choices (see the claude-api guidance):

* **Async** client — the app is async end-to-end.
* **Structured outputs** via ``messages.parse(output_format=...)`` with a Pydantic
  model, so callers get a validated instance and the model retries on schema
  mismatch. No prose parsing anywhere.
* **Prompt caching** of the stable system prompt across a session's steps
  (``cache_control: ephemeral``) — repeated calls pay ~0.1x on the cached prefix.
* **Adaptive thinking** for the hard steps (estimate, BKP); plain calls otherwise.
* Default generator model **Opus 4.8**; the critic uses **Sonnet 4.6**.
* Domain errors are mapped to :class:`AiClientError` so the service/router layer
  never imports ``anthropic`` to handle failures.
"""

from __future__ import annotations

from typing import TypeVar

import anthropic
from pydantic import BaseModel

from app.core.config import get_settings

#: Generator model — most capable Opus tier (see claude-api model table).
GENERATOR_MODEL = "claude-opus-4-8"
#: Critic model — a genuinely different, capable, cheaper model for L3 validation.
CRITIC_MODEL = "claude-sonnet-4-6"

#: Conservative output ceiling for the assistant's structured responses.
_MAX_TOKENS = 8000

T = TypeVar("T", bound=BaseModel)


class AiClientError(RuntimeError):
    """Any failure talking to the model, mapped from the SDK's exceptions."""


class AiNotConfiguredError(AiClientError):
    """Raised when no Anthropic API key is configured (feature disabled)."""


class AiClient:
    """Thin wrapper over the async Anthropic client.

    Construct once per request (cheap) or share a module-level instance. The API
    key is read from settings; if absent, :meth:`generate` raises
    :class:`AiNotConfiguredError` so the router can return 503.
    """

    def __init__(self, api_key: str | None = None) -> None:
        if api_key is None:
            secret = get_settings().anthropic_api_key
            api_key = secret.get_secret_value() if secret else None
        self._api_key = api_key
        self._client = (
            anthropic.AsyncAnthropic(api_key=api_key) if api_key else None
        )

    @property
    def configured(self) -> bool:
        return self._client is not None

    async def generate(
        self,
        *,
        system: str,
        prompt: str,
        schema: type[T],
        thinking: bool = False,
        model: str | None = None,
    ) -> T:
        """Run one structured-output request and return a validated model.

        ``system`` is cached across calls in a session (place stable content
        here). ``prompt`` holds the per-step volatile content. ``schema`` is the
        Pydantic model the response is parsed and validated against.
        """
        if self._client is None:
            raise AiNotConfiguredError(
                "Anthropic API key is not configured (RENO_ANTHROPIC_API_KEY)."
            )

        kwargs: dict = {
            "model": model or GENERATOR_MODEL,
            "max_tokens": _MAX_TOKENS,
            # Stable system prompt, cached so repeated steps reuse the prefix.
            "system": [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [{"role": "user", "content": prompt}],
            "output_format": schema,
        }
        if thinking:
            kwargs["thinking"] = {"type": "adaptive"}

        try:
            response = await self._client.messages.parse(**kwargs)
        except anthropic.APIError as exc:  # network / 4xx / 5xx / refusal
            raise AiClientError(str(exc)) from exc

        parsed = response.parsed_output
        if parsed is None:
            # Refusal or unparseable output — surface as a domain error.
            raise AiClientError(
                "Model returned no parseable output (possible refusal)."
            )
        return parsed
