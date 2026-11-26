"""The Gemini version of the AI interface (Google's official `google-genai` SDK).

We use Gemini because its free tier needs no payment card. Free-tier prompts
may be used by Google to improve its products, which is acceptable here only
because we send nothing but public posts.

Structured outputs: we pass the Pydantic model's JSON schema, Gemini answers
with JSON in that shape, and we validate it again with Pydantic.

Reliability and speed on the free tier (found in live tests on Nov 26):
models are sometimes overloaded (503), slow, or the connection drops. Nobody
should wait long in a demo, so every call has a hard time budget:
- a dropped connection is retried once on the same model;
- a busy or slow model is skipped straight away for the next backup model;
- when the budget runs out we raise `AIUnavailable`, and `FallbackLLM` answers
  with the keyword rules instead.
"""

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import TypeVar

import httpx2 as httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from app.ai.client import AIError, Effort

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Low thinking keeps answers fast: sorting and short replies don't need long
# reasoning. (We measured on Nov 26: "minimal" is rejected by some Flash models
# and was much slower on others, so "low" is the fastest level that works.)
THINKING: dict[Effort, types.ThinkingLevel] = {
    "low": types.ThinkingLevel.LOW,
    "medium": types.ThinkingLevel.LOW,
    "high": types.ThinkingLevel.MEDIUM,
}
# Finish reasons that mean Gemini blocked the answer for safety or policy reasons.
BLOCKED = {
    types.FinishReason.SAFETY,
    types.FinishReason.PROHIBITED_CONTENT,
    types.FinishReason.BLOCKLIST,
    types.FinishReason.SPII,
}
# Busy or temporarily broken: worth trying another model.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
REQUEST_TIMEOUT_SECONDS = 30.0  # one request to one model
MIN_TRY_SECONDS = 5.0  # don't start a new try with less time than this left
DROP_RETRY_DELAY_SECONDS = 1.0

# HTTP timeouts only limit the wait *between* bytes, so a slow model can still
# take minutes (we measured 178 s). Each request therefore runs in a worker
# thread and we stop waiting for it at a hard wall-clock limit.
_WORKERS = ThreadPoolExecutor(max_workers=8, thread_name_prefix="gemini")


class AIUnavailable(AIError):
    """The model is busy, slow or unreachable right now; another model may work."""


class ConnectionDropped(AIUnavailable):
    """The connection broke mid-request; the same model may work on a second try."""


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        *,
        backup_models: Mapping[str, Sequence[str]] | None = None,
        time_budget_seconds: float = 45.0,
        request_timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
        http_client: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        # We handle retries ourselves (see the module docstring), so the SDK's are off.
        options = types.HttpOptions(
            timeout=int(REQUEST_TIMEOUT_SECONDS * 1000), httpx_client=http_client
        )
        self._client = genai.Client(api_key=api_key, http_options=options)
        self._backup_models = {k: list(v) for k, v in (backup_models or {}).items()}
        self._budget = time_budget_seconds
        self._request_timeout = request_timeout_seconds
        self._clock = clock  # tests pass a fake clock and sleep, so they never wait
        self._sleep = sleep
        # Read by `model_used()`, so results are saved with the model that answered.
        self.last_model_used: str | None = None

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
        deadline = self._clock() + self._budget
        chain = [model] + [m for m in self._backup_models.get(model, []) if m != model]
        last_error: AIUnavailable | None = None
        for current in chain:
            retried_drop = False
            while True:
                remaining = deadline - self._clock()
                if remaining < MIN_TRY_SECONDS:
                    raise last_error or AIUnavailable("The AI took too long to answer.")
                timeout = min(self._request_timeout, remaining)
                config = _config(system, schema, effort, max_tokens, timeout)
                try:
                    result = self._call_with_limit(current, user, config, schema, timeout)
                except ConnectionDropped as exc:
                    logger.warning("Gemini %s connection dropped: %s", current, exc)
                    last_error = exc
                    if retried_drop:
                        break  # dropped twice: try the next model
                    retried_drop = True
                    self._sleep(DROP_RETRY_DELAY_SECONDS)
                    continue
                except AIUnavailable as exc:
                    logger.warning("Gemini %s unavailable, trying the next model: %s", current, exc)
                    last_error = exc
                    break
                self.last_model_used = current
                return result
        assert last_error is not None
        raise last_error

    def _call_with_limit(
        self,
        model: str,
        user: str,
        config: types.GenerateContentConfig,
        schema: type[T],
        timeout: float,
    ) -> T:
        future = _WORKERS.submit(self._call, model, user, config, schema)
        try:
            return future.result(timeout=timeout)
        except FutureTimeout as exc:
            # The worker finishes or times out on its own; we just stop waiting.
            raise AIUnavailable("The AI took too long to answer.") from exc

    def _call(
        self, model: str, user: str, config: types.GenerateContentConfig, schema: type[T]
    ) -> T:
        try:
            response = self._client.models.generate_content(
                model=model, contents=user, config=config
            )
        except errors.APIError as exc:
            raise _api_error(exc) from exc
        except httpx.TimeoutException as exc:
            raise AIUnavailable("The AI took too long to answer.") from exc
        except httpx.TransportError as exc:  # dropped connection, DNS, refused ...
            raise ConnectionDropped("Could not reach the AI service.") from exc

        if response.prompt_feedback and response.prompt_feedback.block_reason:
            raise AIError("The AI declined to process this content.")
        candidate = response.candidates[0] if response.candidates else None
        if candidate is None:
            raise AIError("The AI returned no answer. Please try again.")
        if candidate.finish_reason in BLOCKED:
            raise AIError("The AI declined to process this content.")
        if candidate.finish_reason == types.FinishReason.MAX_TOKENS:
            raise AIError("The AI response was incomplete. Please try again.")
        try:
            return schema.model_validate_json(response.text or "")
        except ValidationError as exc:
            raise AIError("The AI declined or returned an unreadable response.") from exc


def _config(
    system: str, schema: type[BaseModel], effort: Effort, max_tokens: int, timeout: float
) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_json_schema=schema.model_json_schema(),
        max_output_tokens=max_tokens,
        thinking_config=types.ThinkingConfig(thinking_level=THINKING[effort]),
        http_options=types.HttpOptions(timeout=int(timeout * 1000)),
    )


def _api_error(exc: errors.APIError) -> AIError:
    if exc.code in (401, 403) or "API key" in (exc.message or ""):
        return AIError("The Gemini API key is invalid.")
    if exc.code == 429:
        return AIUnavailable("The AI free-tier limit was reached. Please try again later.")
    if exc.code in RETRYABLE_STATUS:
        logger.error("Gemini API error %s: %s", exc.code, exc.message)
        return AIUnavailable(f"The AI service is busy or returned an error ({exc.code}).")
    logger.error("Gemini rejected the request %s: %s", exc.code, exc.message)
    return AIError(f"The AI service rejected the request ({exc.code}).")
