"""Bluesky connector tests. The network is replaced by httpx's MockTransport,
so these tests are fast, free and never depend on Bluesky being up."""

import json
from collections.abc import Callable

import httpx2 as httpx
import pytest

from app.connectors.base import ConnectorError
from app.connectors.bluesky import BlueskyConnector
from app.db.enums import Platform

Handler = Callable[[httpx.Request], httpx.Response]


def api_post(n: int) -> dict[str, object]:
    return {
        "uri": f"at://did:plc:abc123/app.bsky.feed.post/rkey{n}",
        "author": {"handle": "maya.bsky.social", "displayName": "Maya"},
        "record": {
            "text": f"We just had our baby! #{n}",
            "createdAt": "2026-11-24T10:00:00.000Z",
            "langs": ["en"],
        },
        "likeCount": 4,
        "replyCount": 1,
        "repostCount": 0,
    }


def make_connector(handler: Handler) -> BlueskyConnector:
    client = httpx.Client(base_url="https://bsky.test", transport=httpx.MockTransport(handler))
    return BlueskyConnector("me.bsky.social", "app-pass", client=client)


def login_ok() -> httpx.Response:
    return httpx.Response(200, json={"accessJwt": "token-1"})


def test_search_logs_in_and_normalizes_posts() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("createSession"):
            assert json.loads(request.content) == {
                "identifier": "me.bsky.social",
                "password": "app-pass",
            }
            return login_ok()
        return httpx.Response(200, json={"posts": [api_post(1)]})

    posts = make_connector(handler).search("new baby", limit=5, language="en")

    assert len(posts) == 1
    post = posts[0]
    assert post.platform == Platform.BLUESKY
    assert post.url == "https://bsky.app/profile/maya.bsky.social/post/rkey1"
    assert post.language == "en"
    assert post.posted_at.year == 2026 and post.posted_at.tzinfo is not None
    assert post.matched_keyword == "new baby"
    search_request = seen[1]
    assert search_request.headers["Authorization"] == "Bearer token-1"
    assert search_request.url.params["q"] == "new baby"
    assert search_request.url.params["lang"] == "en"


def test_search_follows_cursor_until_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("createSession"):
            return login_ok()
        page = 2 if request.url.params.get("cursor") == "next" else 1
        start = 0 if page == 1 else 2
        return httpx.Response(
            200,
            json={"posts": [api_post(start), api_post(start + 1)], "cursor": "next"},
        )

    posts = make_connector(handler).search("baby", limit=3)

    assert [p.external_id[-5:] for p in posts] == ["rkey0", "rkey1", "rkey2"]


def test_bad_credentials_raise_clear_error() -> None:
    connector = make_connector(lambda request: httpx.Response(401, json={"error": "AuthFailed"}))

    with pytest.raises(ConnectorError, match="login failed"):
        connector.search("baby")


def test_rate_limit_raises_clear_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("createSession"):
            return login_ok()
        return httpx.Response(429)

    with pytest.raises(ConnectorError, match="rate limit"):
        make_connector(handler).search("baby")


def test_expired_token_triggers_one_relogin() -> None:
    logins = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal logins
        if request.url.path.endswith("createSession"):
            logins += 1
            return httpx.Response(200, json={"accessJwt": f"token-{logins}"})
        if request.headers["Authorization"] == "Bearer token-1":
            return httpx.Response(400, json={"error": "ExpiredToken"})
        return httpx.Response(200, json={"posts": [api_post(1)]})

    posts = make_connector(handler).search("baby")

    assert logins == 2
    assert len(posts) == 1


def test_missing_credentials_rejected_early() -> None:
    with pytest.raises(ConnectorError):
        BlueskyConnector("", "")
