"""Try a connector from the command line, without the web app.

python -m app.connectors.cli bluesky "new baby" --limit 5
python -m app.connectors.cli sample "#firsthome"
"""

import argparse

from app.connectors.base import ConnectorError, SourceConnector
from app.connectors.bluesky import BlueskyConnector
from app.connectors.sample import SampleConnector
from app.core.config import get_settings


def build_connector(name: str) -> SourceConnector:
    if name == "sample":
        return SampleConnector()
    settings = get_settings()
    password = settings.bluesky_app_password
    return BlueskyConnector(
        settings.bluesky_handle or "",
        password.get_secret_value() if password else "",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=["bluesky", "sample"])
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--lang", default=None)
    args = parser.parse_args()

    try:
        posts = build_connector(args.source).search(
            args.query, limit=args.limit, language=args.lang
        )
    except ConnectorError as exc:
        raise SystemExit(f"Error: {exc}") from exc

    print(f"{len(posts)} post(s) for {args.query!r} from {args.source}\n")
    for post in posts:
        print(f"[{post.posted_at:%Y-%m-%d %H:%M}] @{post.author_handle}")
        print(f"  {post.text[:200]!r}")
        print(f"  {post.url}\n")


if __name__ == "__main__":
    main()
