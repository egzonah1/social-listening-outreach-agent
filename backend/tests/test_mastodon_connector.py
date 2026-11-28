"""Mastodon connector tests. The network is replaced by httpx's MockTransport."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx2 as httpx
import pytest

from app.connectors.base import ConnectorError
from app.connectors.mastodon import MastodonConnector, html_to_text, to_hashtag
from app.db.enums import Platform

Handler = Callable[[httpx.Request], httpx.Response]


def status(n: int, **overrides: Any) -> dict[str, Any]:
    account: dict[str, Any] = {
        "acct": "maya",
        "display_name": "Maya",
        "bot": False,
        "noindex": False,
    }
    account.update(overrides.pop("account", {}))
    data: dict[str, Any] = {
        "id": str(1000 - n),
        "url": f"https://mastodon.test/@maya/{1000 - n}",
        "uri": f"https://mastodon.test/users/maya/statuses/{1000 - n}",
        "created_at": f"2026-11-2{n % 8}T10:00:00.000Z",
        "content": f"<p>We just had our baby! <a href='#'>#newbaby</a> {n}</p>",
        "language": "en",
        "visibility": "public",
        "reblog": None,
        "favourites_count": 3,
        "replies_count": 1,
        "reblogs_count": 0,
        "account": account,
    }
    data.update(overrides)
    return data


def make_connector(handler: Handler) -> MastodonConnector:
    client = httpx.Client(base_url="https://mastodon.test", transport=httpx.MockTransport(handler))
    return MastodonConnector("https://mastodon.test", client=client)


def test_keywords_become_hashtags() -> None:
    assert to_hashtag("new baby") == "newbaby"
    assert to_hashtag("#Newborn") == "newborn"
    assert to_hashtag("got the keys!") == "gotthekeys"
    assert to_hashtag("  ") == ""


def test_html_is_turned_into_plain_text() -> None:
    html = "<p>First line<br>second line</p><p>New &amp; <a href='x'>#tag</a></p>"
    assert html_to_text(html) == "First line\nsecond line\n\nNew & #tag"


def test_search_reads_the_hashtag_timeline_and_normalizes() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[status(1)])

    posts = make_connector(handler).search("new baby", limit=5)

    assert seen[0].url.path == "/api/v1/timelines/tag/newbaby"
    assert "Authorization" not in seen[0].headers  # public endpoint, no account
    assert len(posts) == 1
    post = posts[0]
    assert post.platform == Platform.MASTODON
    assert post.external_id == "mastodon.test/999"
    assert post.author_handle == "maya@mastodon.test"
    assert post.text == "We just had our baby! #newbaby 1"
    assert post.matched_keyword == "new baby"
    assert post.like_count == 3 and post.posted_at.tzinfo is not None


def test_search_skips_non_public_bots_noindex_and_boosts() -> None:
    statuses = [
        status(1),
        status(2, visibility="unlisted"),
        status(3, account={"bot": True}),
        status(4, account={"noindex": True}),
        status(5, reblog={"id": "1"}),
        status(6, account={"acct": "sam@other.social"}),
    ]
    posts = make_connector(lambda _: httpx.Response(200, json=statuses)).search("baby", limit=10)

    assert [p.external_id for p in posts] == ["mastodon.test/999", "mastodon.test/994"]
    assert posts[1].author_handle == "sam@other.social"


def test_search_filters_language_but_keeps_unknown() -> None:
    statuses = [status(1), status(2, language="de"), status(3, language=None)]
    posts = make_connector(lambda _: httpx.Response(200, json=statuses)).search(
        "baby", language="en"
    )
    assert [p.language for p in posts] == ["en", None]


def test_search_pages_with_max_id_until_limit() -> None:
    seen: list[httpx.Request] = []
    first_page = [status(n % 7, id=str(500 - n)) for n in range(40)]
    second_page = [status(n % 7, id=str(400 - n)) for n in range(40)]

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        page = second_page if request.url.params.get("max_id") == "461" else first_page
        return httpx.Response(200, json=page)

    posts = make_connector(handler).search("baby", limit=45)

    assert len(posts) == 45
    assert len(seen) == 2
    assert seen[1].url.params["max_id"] == "461"


def test_search_stops_at_since() -> None:
    statuses = [status(5), status(1)]  # 25 Nov, then 21 Nov
    posts = make_connector(lambda _: httpx.Response(200, json=statuses)).search(
        "baby", since=datetime(2026, 11, 23, tzinfo=UTC)
    )
    assert len(posts) == 1


def test_empty_hashtag_makes_no_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    assert make_connector(handler).search("!!!") == []


@pytest.mark.parametrize(
    ("code", "message"),
    [(429, "rate limit"), (401, "does not allow"), (500, "HTTP 500")],
)
def test_errors_become_connector_errors(code: int, message: str) -> None:
    connector = make_connector(lambda _: httpx.Response(code, json={}))
    with pytest.raises(ConnectorError, match=message):
        connector.search("baby")


def test_still_available_drops_deleted_and_hidden_posts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        status_id = request.url.path.rsplit("/", 1)[-1]
        if status_id == "1":
            return httpx.Response(200, json=status(999))
        if status_id == "2":
            return httpx.Response(404, json={"error": "Record not found"})
        return httpx.Response(200, json=status(997, visibility="private"))

    ids = ["mastodon.test/1", "mastodon.test/2", "mastodon.test/3", "other.social/4"]
    assert make_connector(handler).still_available(ids) == {"mastodon.test/1"}


def test_instance_must_be_a_url() -> None:
    with pytest.raises(ConnectorError):
        MastodonConnector("mastodon.social")


def test_registry_builds_mastodon_without_credentials() -> None:
    from app.connectors.registry import get_connector
    from app.core.config import Settings

    connector = get_connector(
        Platform.MASTODON, Settings(mastodon_instance="https://fosstodon.org")
    )
    assert isinstance(connector, MastodonConnector)
