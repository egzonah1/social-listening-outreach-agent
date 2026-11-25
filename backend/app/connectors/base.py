"""The contract every data source implements.

The rest of the app only knows about `SourceConnector` and `NormalizedPost`,
never about Bluesky or Mastodon JSON. Adding a platform means adding one
module that implements `search()`; nothing else changes.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.db.enums import Platform


@dataclass(frozen=True, slots=True)
class NormalizedPost:
    """A public post in a platform-independent shape."""

    platform: Platform
    external_id: str
    url: str
    author_handle: str
    author_display_name: str | None
    text: str
    language: str | None
    posted_at: datetime
    like_count: int = 0
    reply_count: int = 0
    repost_count: int = 0
    matched_keyword: str | None = None
    is_sample: bool = False


class ConnectorError(Exception):
    """A source failed in a way the user should see (bad credentials, rate limit, outage)."""


class SourceConnector(Protocol):
    platform: Platform

    def search(
        self,
        query: str,
        *,
        limit: int = 25,
        since: datetime | None = None,
        language: str | None = None,
    ) -> list[NormalizedPost]:
        """Return public posts matching `query` (a keyword, phrase or #hashtag)."""
        ...
