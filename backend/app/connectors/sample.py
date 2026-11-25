"""Sample connector: hand-written demo posts, clearly labelled as sample data.

These posts are fictional and were written for this project. They exist so
the demo and tests work even when a real API is down or rate-limited, and they
cover sensitive cases (grief, baby loss) that the triage step must handle.
The UI marks every sample post with a "Sample" badge.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.connectors.base import NormalizedPost
from app.db.enums import Platform

DATA_FILE = Path(__file__).with_name("sample_posts.json")


class SampleConnector:
    platform = Platform.SAMPLE

    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime.now(UTC)
        self._posts: list[dict[str, Any]] = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    def search(
        self,
        query: str,
        *,
        limit: int = 25,
        since: datetime | None = None,
        language: str | None = None,
    ) -> list[NormalizedPost]:
        # Match every word of the query, ignoring case and "#", like a simple search engine.
        terms = [t.lstrip("#").lower() for t in query.split() if t.strip("#")]
        matches: list[NormalizedPost] = []
        for item in self._posts:
            haystack = item["text"].lower().replace("#", "")
            if not all(term in haystack for term in terms):
                continue
            post = self._to_post(item, query)
            if since and post.posted_at < since:
                continue
            matches.append(post)
        matches.sort(key=lambda p: p.posted_at, reverse=True)  # newest first
        return matches[:limit]

    def _to_post(self, item: dict[str, Any], query: str) -> NormalizedPost:
        return NormalizedPost(
            platform=Platform.SAMPLE,
            external_id=item["id"],
            url=f"sample://posts/{item['id']}",
            author_handle=item["handle"],
            author_display_name=item["name"],
            text=item["text"],
            language="en",
            posted_at=self._now - timedelta(hours=item["hours_ago"]),
            matched_keyword=query,
            is_sample=True,
        )
