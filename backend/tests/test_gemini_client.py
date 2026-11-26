"""Checks our GeminiClient against the real google-genai SDK, with the network faked."""

import json
from collections.abc import Callable
from typing import Any

import httpx2 as httpx
import pytest

from app.ai.client import AIError
from app.ai.gemini import ATTEMPTS_PER_MODEL, AIUnavailable, GeminiClient
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


def make_client(handler: Handler, backups: dict[str, str] | None = None) -> GeminiClient:
    return GeminiClient(
        "test-key",
        backup_models=backups,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda seconds: None,  # don't really wait between retries
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
    assert (thinking.get("thinkingLevel") or thinking.get("thinking_level")) == "MINIMAL"


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


def test_server_error_is_retried_then_becomes_clear_error() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return error(503, "UNAVAILABLE", "This model is currently experiencing high demand.")

    with pytest.raises(AIUnavailable, match=r"busy .*\(503\)"):
        call(make_client(handler))
    assert len(calls) == ATTEMPTS_PER_MODEL


def test_dropped_connection_is_retried() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
        return httpx.Response(200, json=answer(json.dumps(DRAFTS)))

    client = make_client(handler)
    result = call(client)

    assert result.variants[0].text == "Congratulations!"
    assert len(attempts) == 2
    assert client.last_model_used == "gemini-test"


def test_backup_model_is_used_when_main_model_is_busy() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if "gemini-test:" in request.url.path:
            return error(503, "UNAVAILABLE")
        return httpx.Response(200, json=answer(json.dumps(DRAFTS)))

    client = make_client(handler, backups={"gemini-test": "gemini-backup"})
    result = call(client)

    assert result.variants[0].text == "Congratulations!"
    assert [p.rsplit("/", 1)[1] for p in paths] == [
        "gemini-test:generateContent",
        "gemini-test:generateContent",
        "gemini-backup:generateContent",
    ]
    assert client.last_model_used == "gemini-backup"


def test_bad_request_is_not_retried() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return error(400, "INVALID_ARGUMENT", "Bad schema.")

    with pytest.raises(AIError, match=r"rejected the request \(400\)"):
        call(make_client(handler, backups={"gemini-test": "gemini-backup"}))
    assert len(calls) == 1
