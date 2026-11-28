"""Builds the right connector for a platform from app settings."""

from collections.abc import Callable

from app.connectors.base import ConnectorError, SourceConnector
from app.connectors.bluesky import BlueskyConnector
from app.connectors.mastodon import MastodonConnector
from app.connectors.sample import SampleConnector
from app.core.config import Settings, get_settings
from app.db.enums import Platform

ConnectorFactory = Callable[[Platform], SourceConnector]


def get_connector(platform: Platform, settings: Settings | None = None) -> SourceConnector:
    settings = settings or get_settings()
    if platform == Platform.SAMPLE:
        return SampleConnector()
    if platform == Platform.BLUESKY:
        if not settings.bluesky_handle or not settings.bluesky_app_password:
            raise ConnectorError("Bluesky is not configured on the server.")
        return BlueskyConnector(
            settings.bluesky_handle, settings.bluesky_app_password.get_secret_value()
        )
    if platform == Platform.MASTODON:
        return MastodonConnector(settings.mastodon_instance)
    raise ConnectorError(f"{platform.value} is not supported yet.")
