"""Checks our GeminiClient against the real google-genai SDK, with the network faked."""

import json
from collections.abc import Callable
from typing import Any

import httpx2 as httpx
import pytest

from app.ai.client import AIError
from app.ai.gemini import AIUnavailable, GeminiClient
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


class FakeClock:
    """Time that only moves when a test (or the fake network) moves it."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def make_client(
    handler: Handler,
    backups: dict[str, list[str]] | None = None,
    clock: FakeClock | None = None,
) -> GeminiClient:
    clock = clock or FakeClock()
    return GeminiClient(
        "test-key",
        backup_models=backups,
        time_budget_seconds=45,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        clock=clock,
        sleep=clock.sleep,
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


def test_busy_model_without_backup_becomes_clear_error_at_once() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return error(503, "UNAVAILABLE", "This model is currently experiencing high demand.")

    with pytest.raises(AIUnavailable, match=r"busy .*\(503\)"):
        call(make_client(handler))
    assert len(calls) == 1  # no waiting on a busy model


def test_dropped_connection_is_retried_once_on_the_same_model() -> None:
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


def test_busy_model_goes_straight_to_the_backup_models_in_order() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        name = request.url.path.rsplit("/", 1)[1].split(":")[0]
        paths.append(name)
        if name == "gemini-test":
            return error(503, "UNAVAILABLE")
        if name == "backup-1":
            raise httpx.ReadTimeout("slow")
        return httpx.Response(200, json=answer(json.dumps(DRAFTS)))

    client = make_client(handler, backups={"gemini-test": ["backup-1", "backup-2"]})
    result = call(client)

    assert result.variants[0].text == "Congratulations!"
    assert paths == ["gemini-test", "backup-1", "backup-2"]
    assert client.last_model_used == "backup-2"


def test_stops_when_the_time_budget_is_used_up() -> None:
    clock = FakeClock()
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        clock.now += 30  # every model "hangs" for 30 seconds, then times out
        raise httpx.ReadTimeout("slow")

    client = make_client(handler, backups={"gemini-test": ["b1", "b2", "b3"]}, clock=clock)
    with pytest.raises(AIUnavailable, match="too long"):
        call(client)

    assert len(paths) == 2  # 30 s + 15 s = the 45 s budget; no third try
    assert clock.now <= 60


def test_each_request_gets_at_most_the_remaining_time() -> None:
    timeouts: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        timeouts.append(request.extensions["timeout"]["read"])
        return httpx.Response(200, json=answer(json.dumps(DRAFTS)))

    call(make_client(handler))

    assert timeouts == [30.0]


def test_bad_request_is_not_retried() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return error(400, "INVALID_ARGUMENT", "Bad schema.")

    with pytest.raises(AIError, match=r"rejected the request \(400\)"):
        call(make_client(handler, backups={"gemini-test": ["gemini-backup"]}))
    assert len(calls) == 1


def test_a_hanging_request_is_abandoned_at_the_hard_limit() -> None:
    import time as real_time

    def handler(request: httpx.Request) -> httpx.Response:
        if "gemini-test:" in request.url.path:
            real_time.sleep(1.0)  # keeps "streaming" past our limit
        return httpx.Response(200, json=answer(json.dumps(DRAFTS)))

    client = GeminiClient(
        "test-key",
        backup_models={"gemini-test": ["gemini-backup"]},
        request_timeout_seconds=0.2,
        time_budget_seconds=10,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    started = real_time.monotonic()
    result = call(client)

    assert result.variants[0].text == "Congratulations!"
    assert client.last_model_used == "gemini-backup"
    assert real_time.monotonic() - started < 0.9
