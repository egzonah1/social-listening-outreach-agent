"""Checks our ClaudeClient against the real Anthropic SDK, with the network faked."""

import json
from collections.abc import Callable
from typing import Any

import anthropic
import httpx2 as httpx
import pytest

from app.ai.client import AIError, ClaudeClient
from app.ai.schemas import DraftSet

Handler = Callable[[httpx.Request], httpx.Response]
DRAFTS = {"variants": [{"tone": "warm", "text": "Congratulations!"}]}


def api_message(text: str, stop_reason: str = "end_turn") -> dict[str, Any]:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def make_client(handler: Handler) -> ClaudeClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    sdk = anthropic.Anthropic(api_key="test-key", http_client=http, max_retries=0)
    return ClaudeClient("test-key", client=sdk)


def call(client: ClaudeClient, model: str = "claude-opus-5-5") -> DraftSet:
    return client.parse(model=model, system="sys", user="hi", schema=DraftSet)


def test_parses_structured_output_and_sends_expected_request() -> None:
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append({"body": json.loads(request.content), "headers": request.headers})
        return httpx.Response(200, json=api_message(json.dumps(DRAFTS)))

    result = call(make_client(handler))

    assert result.variants[0].text == "Congratulations!"
    body = sent[0]["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["output_config"]["effort"] == "medium"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["fallbacks"] == "default"  # Opus gets the safety fallback
    assert "server-side-fallback" in sent[0]["headers"]["anthropic-beta"]


def test_haiku_requests_have_no_fallback() -> None:
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=api_message(json.dumps(DRAFTS)))

    call(make_client(handler), model="claude-haiku-5-5")

    assert "fallbacks" not in sent[0]


def test_refusal_becomes_clear_error() -> None:
    client = make_client(lambda r: httpx.Response(200, json=api_message("", "refusal")))

    with pytest.raises(AIError, match="declined"):
        call(client)


def test_bad_api_key_becomes_clear_error() -> None:
    error = {"type": "error", "error": {"type": "authentication_error", "message": "bad"}}
    client = make_client(lambda r: httpx.Response(401, json=error))

    with pytest.raises(AIError, match="API key"):
        call(client)
