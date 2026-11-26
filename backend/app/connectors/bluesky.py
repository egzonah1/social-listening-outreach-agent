"""Bluesky connector using the official AT Protocol API.

Docs: https://docs.bsky.app/docs/api/app-bsky-feed-search-posts

Search needs an authenticated session (the public endpoint can refuse
unauthenticated search under load), so we log in with an *app password*
from a dedicated account. The connector only ever calls read endpoints:
it cannot post, like or message anyone.

Respecting authors' choices: Bluesky lets people ask that their posts are not
shown to logged-out viewers (the "!no-unauthenticated" self-label). We are
logged in, so we could see them, but we skip those accounts anyway: the person
has said they don't want wide visibility.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import httpx2 as httpx

from app.connectors.base import ConnectorError, NormalizedPost
from app.db.enums import Platform

DEFAULT_SERVICE = "https://bsky.social"
MAX_PAGE_SIZE = 100  # API maximum for searchPosts
MAX_URIS_PER_LOOKUP = 25  # API maximum for getPosts
OPT_OUT_LABEL = "!no-unauthenticated"


class BlueskyConnector:
    platform = Platform.BLUESKY

    def __init__(
        self,
        handle: str,
        app_password: str,
        *,
        service_url: str = DEFAULT_SERVICE,
        client: httpx.Client | None = None,
    ) -> None:
        if not handle or not app_password:
            raise ConnectorError("Bluesky handle and app password are required.")
        self._handle = handle
        self._app_password = app_password
        # Injecting the HTTP client lets tests replace the network with fakes.
        self._client = client or httpx.Client(base_url=service_url, timeout=15.0)
        self._access_token: str | None = None

    # ---- public API -------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        limit: int = 25,
        since: datetime | None = None,
        language: str | None = None,
    ) -> list[NormalizedPost]:
        results: list[NormalizedPost] = []
        cursor: str | None = None
        while len(results) < limit:
            params: dict[str, str | int] = {
                "q": query,
                "limit": min(MAX_PAGE_SIZE, limit - len(results)),
                "sort": "latest",
            }
            if since:
                params["since"] = since.astimezone(UTC).isoformat().replace("+00:00", "Z")
            if language:
                params["lang"] = language
            if cursor:
                params["cursor"] = cursor

            data = self._get("/xrpc/app.bsky.feed.searchPosts", params)
            posts = data.get("posts", [])
            results.extend(self._normalize(p, query) for p in posts if not _opted_out(p))
            cursor = data.get("cursor")
            if not cursor or not posts:
                break
        return results[:limit]

    def still_available(self, external_ids: Sequence[str]) -> set[str]:
        """Look posts up by URI. Deleted posts are simply missing from the answer."""
        available: set[str] = set()
        ids = list(external_ids)
        for start in range(0, len(ids), MAX_URIS_PER_LOOKUP):
            chunk = ids[start : start + MAX_URIS_PER_LOOKUP]
            data = self._get("/xrpc/app.bsky.feed.getPosts", {"uris": chunk})
            available.update(p["uri"] for p in data.get("posts", []) if not _opted_out(p))
        return available

    # ---- internals --------------------------------------------------------

    def _login(self) -> None:
        response = self._client.post(
            "/xrpc/com.atproto.server.createSession",
            json={"identifier": self._handle, "password": self._app_password},
        )
        if response.status_code == 401:
            raise ConnectorError("Bluesky login failed: check the handle and app password.")
        self._raise_for_status(response)
        self._access_token = response.json()["accessJwt"]

    def _get(self, path: str, params: Mapping[str, str | int | list[str]]) -> dict[str, Any]:
        if self._access_token is None:
            self._login()
        response = self._client.get(path, params=params, headers=self._auth_header())
        if response.status_code in (400, 401) and _is_expired_token(response):
            # Access tokens are short-lived: log in again once and retry.
            self._login()
            response = self._client.get(path, params=params, headers=self._auth_header())
        self._raise_for_status(response)
        body: dict[str, Any] = response.json()
        return body

    def _auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code == 429:
            raise ConnectorError("Bluesky rate limit reached. Try again in a few minutes.")
        if response.is_error:
            raise ConnectorError(f"Bluesky returned HTTP {response.status_code}.")

    @staticmethod
    def _normalize(post: dict[str, Any], query: str) -> NormalizedPost:
        author = post["author"]
        record = post.get("record", {})
        uri: str = post["uri"]  # at://did:plc:xyz/app.bsky.feed.post/<rkey>
        rkey = uri.rsplit("/", 1)[-1]
        langs = record.get("langs") or []
        created = record.get("createdAt") or post.get("indexedAt")
        return NormalizedPost(
            platform=Platform.BLUESKY,
            external_id=uri,
            url=f"https://bsky.app/profile/{author['handle']}/post/{rkey}",
            author_handle=author["handle"],
            author_display_name=author.get("displayName") or None,
            text=record.get("text", ""),
            language=langs[0] if langs else None,
            posted_at=_parse_datetime(created),
            like_count=post.get("likeCount", 0),
            reply_count=post.get("replyCount", 0),
            repost_count=post.get("repostCount", 0),
            matched_keyword=query,
        )


def _opted_out(post: dict[str, Any]) -> bool:
    labels = post.get("author", {}).get("labels") or []
    return any(label.get("val") == OPT_OUT_LABEL for label in labels)


def _is_expired_token(response: httpx.Response) -> bool:
    try:
        return bool(response.json().get("error") in {"ExpiredToken", "InvalidToken"})
    except ValueError:
        return False


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
