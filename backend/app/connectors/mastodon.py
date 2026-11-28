"""Mastodon connector using the official, public Mastodon REST API.

Docs: https://docs.joinmastodon.org/methods/timelines/#tag

Why hashtag timelines and not full-text search: on Mastodon, full-text search
only covers posts whose authors opted in, and it needs a logged-in account.
Hashtags are how people on Mastodon choose to make a post discoverable, and the
hashtag timeline is public and needs no account or key. So each keyword is
turned into a hashtag ("new baby" -> #newbaby) and we read that timeline on one
instance (mastodon.social by default), which also sees posts from other servers
it federates with.

Respecting authors' choices, we skip:
- posts that are not fully public (unlisted, followers-only, direct),
- accounts that asked not to be indexed ("noindex"),
- bot accounts (they don't have life events).
The connector only calls read endpoints: it cannot post, follow or message anyone.
"""

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx2 as httpx

from app.connectors.base import ConnectorError, NormalizedPost
from app.db.enums import Platform

DEFAULT_INSTANCE = "https://mastodon.social"
MAX_PAGE_SIZE = 40  # API maximum for timelines
MAX_PAGES = 5  # stop early on very quiet hashtags with lots of filtered posts


class MastodonConnector:
    platform = Platform.MASTODON

    def __init__(
        self,
        instance_url: str = DEFAULT_INSTANCE,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._instance_url = instance_url.rstrip("/")
        self._host = urlparse(self._instance_url).netloc
        if not self._host:
            raise ConnectorError(
                "MASTODON_INSTANCE must be a full URL, e.g. https://mastodon.social"
            )
        # Injecting the HTTP client lets tests replace the network with fakes.
        self._client = client or httpx.Client(base_url=self._instance_url, timeout=15.0)

    # ---- public API -------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        limit: int = 25,
        since: datetime | None = None,
        language: str | None = None,
    ) -> list[NormalizedPost]:
        tag = to_hashtag(query)
        if not tag:
            return []
        results: list[NormalizedPost] = []
        max_id: str | None = None
        for _ in range(MAX_PAGES):
            params: dict[str, str | int] = {"limit": MAX_PAGE_SIZE}
            if max_id:
                params["max_id"] = max_id
            statuses = self._get(f"/api/v1/timelines/tag/{tag}", params)
            if not isinstance(statuses, list) or not statuses:
                break
            for status in statuses:
                post = self._normalize(status, query)
                if since and post.posted_at < since:
                    return results[:limit]  # the timeline is newest first
                if _keep(status) and _language_ok(post, language):
                    results.append(post)
            if len(results) >= limit or len(statuses) < MAX_PAGE_SIZE:
                break  # enough posts, or this was the last page
            max_id = str(statuses[-1]["id"])
        return results[:limit]

    def still_available(self, external_ids: Sequence[str]) -> set[str]:
        """Look each status up. Deleted or hidden posts answer 404 (or 410)."""
        available: set[str] = set()
        for external_id in external_ids:
            host, _, status_id = external_id.partition("/")
            if host != self._host or not status_id:
                continue  # collected from another instance; we can't check it here
            response = self._client.get(f"/api/v1/statuses/{status_id}")
            if response.status_code in (404, 410):
                continue
            self._raise_for_status(response)
            if _keep(response.json()):
                available.add(external_id)
        return available

    # ---- internals --------------------------------------------------------

    def _get(self, path: str, params: Mapping[str, str | int]) -> Any:
        response = self._client.get(path, params=params)
        self._raise_for_status(response)
        return response.json()

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code == 429:
            raise ConnectorError("Mastodon rate limit reached. Try again in a few minutes.")
        if response.status_code in (401, 403):
            raise ConnectorError(
                "This Mastodon server does not allow public hashtag timelines. "
                "Set MASTODON_INSTANCE to another server."
            )
        if response.is_error:
            raise ConnectorError(f"Mastodon returned HTTP {response.status_code}.")

    def _normalize(self, status: dict[str, Any], query: str) -> NormalizedPost:
        account = status.get("account", {})
        acct: str = account.get("acct", "")
        handle = acct if "@" in acct else f"{acct}@{self._host}"
        return NormalizedPost(
            platform=Platform.MASTODON,
            external_id=f"{self._host}/{status['id']}",
            url=status.get("url") or status.get("uri", ""),
            author_handle=handle,
            author_display_name=account.get("display_name") or None,
            text=html_to_text(status.get("content", "")),
            language=status.get("language"),
            posted_at=_parse_datetime(status.get("created_at")),
            like_count=status.get("favourites_count", 0),
            reply_count=status.get("replies_count", 0),
            repost_count=status.get("reblogs_count", 0),
            matched_keyword=query,
        )


def to_hashtag(keyword: str) -> str:
    """'new baby' -> 'newbaby', '#Newborn' -> 'newborn'. Letters, digits and _ only."""
    return re.sub(r"[^\w]", "", keyword.lower())


def _keep(status: dict[str, Any]) -> bool:
    account = status.get("account", {})
    return (
        status.get("visibility") == "public"
        and status.get("reblog") is None
        and not account.get("noindex", False)
        and not account.get("bot", False)
    )


def _language_ok(post: NormalizedPost, language: str | None) -> bool:
    # Many posts have no language set; keep those rather than lose them.
    return not language or not post.language or post.language == language


class _TextExtractor(HTMLParser):
    """Mastodon sends post text as HTML. Keep the words, turn paragraphs into lines."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "p":
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    text = "".join(parser.parts)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
