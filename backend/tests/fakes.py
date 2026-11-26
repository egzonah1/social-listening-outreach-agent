"""A fake AI client for tests: returns canned answers and records each call."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel

from app.ai.client import AIError

T = TypeVar("T", bound=BaseModel)


@dataclass
class FakeLLM:
    # Builds the response from the call's arguments (schema, user prompt, ...).
    responder: Callable[..., BaseModel]
    calls: list[dict[str, Any]] = field(default_factory=list)
    error: AIError | None = None

    def parse(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: type[T],
        effort: str = "medium",
        max_tokens: int = 4000,
    ) -> T:
        self.calls.append({"model": model, "system": system, "user": user, "schema": schema})
        if self.error:
            raise self.error
        result = self.responder(schema=schema, user=user)
        assert isinstance(result, schema)
        return result
