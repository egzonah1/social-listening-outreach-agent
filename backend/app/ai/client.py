"""The AI interface the app uses, and its Claude version.

Every AI call in the app goes through `parse()`, which asks a model for output
matching a Pydantic model (structured outputs) and returns that validated
object. Services only know the `StructuredLLM` interface, so the provider can
be swapped (Gemini in `gemini.py`, Claude here, keyword rules in `rules.py`)
without touching them, and tests can swap in a fake.
"""

import logging
from typing import Literal, Protocol, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
Effort = Literal["low", "medium", "high"]

# Opus-class models support a server-side fallback: if a safety classifier
# declines a request (possible with posts about grief or health), the API
# retries it on a suitable model instead of failing.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AIError(Exception):
    """An AI call failed in a way we should show the user."""


class StructuredLLM(Protocol):
    def parse(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: type[T],
        effort: Effort = "medium",
        max_tokens: int = 4000,
    ) -> T: ...


def model_used(ai: StructuredLLM, requested: str) -> str:
    """The name to save with a result. A FallbackLLM records when its backup answered."""
    actual = getattr(ai, "last_model_used", None)
    return actual if isinstance(actual, str) else requested


class ClaudeClient:
    def __init__(self, api_key: str, client: anthropic.Anthropic | None = None) -> None:
        # max_retries: the SDK retries rate limits and server errors with backoff.
        self._client = client or anthropic.Anthropic(api_key=api_key, max_retries=3, timeout=90)

    def parse(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: type[T],
        effort: Effort = "medium",
        max_tokens: int = 4000,
    ) -> T:
        use_fallback = model.startswith("claude-opus")
        try:
            response = self._client.beta.messages.parse(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
                output_config={"effort": effort},
                betas=[FALLBACK_BETA] if use_fallback else anthropic.omit,
                fallbacks="default" if use_fallback else anthropic.omit,
            )
        except anthropic.AuthenticationError as exc:
            raise AIError("The Anthropic API key is invalid.") from exc
        except anthropic.RateLimitError as exc:
            raise AIError("The AI service is busy. Please try again in a minute.") from exc
        except anthropic.APIConnectionError as exc:
            raise AIError("Could not reach the AI service.") from exc
        except anthropic.APIStatusError as exc:
            logger.error("Claude API error %s: %s", exc.status_code, exc.message)
            raise AIError(f"The AI service returned an error ({exc.status_code}).") from exc
        except ValidationError as exc:
            # The SDK validates the output while parsing. An empty or cut-off
            # answer (a refusal, or hitting max_tokens) fails here.
            raise AIError("The AI declined or returned an unreadable response.") from exc

        if response.stop_reason == "refusal":
            raise AIError("The AI declined to process this content.")
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise AIError("The AI response was incomplete. Please try again.")
        result: T = response.parsed_output
        return result
