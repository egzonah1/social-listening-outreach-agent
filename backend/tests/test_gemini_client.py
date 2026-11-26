"""Checks our GeminiClient against the real google-genai SDK, with the network faked."""

import json
from collections.abc import Callable
from typing import Any

import httpx2 as httpx
import pytest

from app.ai.client import AIError
from app.ai.gemini import GeminiClient
from app.ai.schemas import DraftSet, TriageBatch

Handler = Callable[[httpx.Request], httpx.Response]
DRAFTS = {"variants": [{"tone": "warm", "text": "Congratulations!"}]}


def answer(text: str, finish_reason: str = "STOP") -> dict[str, Any]:
    return {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": finish_reason}
        ],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
    }


def error(code: int, status: str, message: str = "nope") -> httpx.Response:
    return httpx.Response(
        code, json={"error": {"code": code, "message": message, "status": status}}
    )


def make_client(handler: Handler) -> GeminiClient:
    return GeminiClient(
        "test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def call(client: GeminiClient, schema: type = DraftSet) -> Any:
    return client.parse(model="gemini-test", system="sys", user="hi", schema=schema, effort="low")


def test_parses_structured_output_and_sends_expected_request() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json=answer(json.dumps(DRAFTS)))

    result = call(make_client(handler))

    assert result.variants[0].text == "Congratulations!"
    request = sent[0]
    assert request.url.path.endswith("/models/gemini-test:generateContent")
    assert request.headers["x-goog-api-key"] == "test-key"
    body = json.loads(request.content)
    assert body["contents"][0]["parts"][0]["text"] == "hi"
    assert body["systemInstruction"]["parts"][0]["text"] == "sys"
    config = body["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert config["responseJsonSchema"]["title"] == "DraftSet"
    thinking = config["thinkingConfig"]  # the SDK sends this one in snake_case
    assert (thinking.get("thinkingLevel") or thinking.get("thinking_level")) == "LOW"


def test_schema_with_nested_models_and_enums_is_sent() -> None:
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=answer('{"results": []}'))

    call(make_client(handler), schema=TriageBatch)

    schema = sent[0]["generationConfig"]["responseJsonSchema"]
    assert "PostTriage" in schema["$defs"]
    assert "Sensitivity" in schema["$defs"]


def test_safety_block_becomes_clear_error() -> None:
    client = make_client(lambda r: httpx.Response(200, json=answer("", "SAFETY")))

    with pytest.raises(AIError, match="declined"):
        call(client)


def test_cut_off_answer_becomes_clear_error() -> None:
    client = make_client(lambda r: httpx.Response(200, json=answer('{"varia', "MAX_TOKENS")))

    with pytest.raises(AIError, match="incomplete"):
        call(client)


def test_invalid_json_becomes_clear_error() -> None:
    client = make_client(lambda r: httpx.Response(200, json=answer('{"variants": "x"}')))

    with pytest.raises(AIError, match="unreadable"):
        call(client)


def test_bad_api_key_becomes_clear_error() -> None:
    client = make_client(lambda r: error(400, "INVALID_ARGUMENT", "API key not valid."))

    with pytest.raises(AIError, match="API key"):
        call(client)


def test_free_tier_limit_becomes_clear_error() -> None:
    client = make_client(lambda r: error(429, "RESOURCE_EXHAUSTED"))

    with pytest.raises(AIError, match="free-tier limit"):
        call(client)


def test_server_error_becomes_clear_error() -> None:
    client = make_client(lambda r: error(503, "UNAVAILABLE"))

    with pytest.raises(AIError, match=r"error \(503\)"):
        call(client)
