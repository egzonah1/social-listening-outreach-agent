from datetime import UTC, datetime, timedelta

from app.connectors.sample import SampleConnector
from app.db.enums import Platform

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)


def test_hashtag_and_plain_word_match_the_same_posts() -> None:
    connector = SampleConnector(now=NOW)

    with_hash = [p.external_id for p in connector.search("#firsthome")]
    without_hash = [p.external_id for p in connector.search("firsthome")]

    assert with_hash and with_hash == without_hash


def test_all_query_words_must_match() -> None:
    posts = SampleConnector(now=NOW).search("new baby")

    assert posts
    assert all("new" in p.text.lower() and "baby" in p.text.lower() for p in posts)


def test_results_are_labelled_sorted_and_limited() -> None:
    posts = SampleConnector(now=NOW).search("baby", limit=3)

    assert len(posts) == 3
    assert all(p.is_sample and p.platform == Platform.SAMPLE for p in posts)
    assert [p.posted_at for p in posts] == sorted((p.posted_at for p in posts), reverse=True)


def test_since_filters_old_posts() -> None:
    since = NOW - timedelta(hours=24)

    posts = SampleConnector(now=NOW).search("baby", since=since)

    assert posts
    assert all(p.posted_at >= since for p in posts)
