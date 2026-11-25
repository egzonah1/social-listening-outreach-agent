"""Fixed vocabularies used across the database, the API and the AI prompts.

They are stored as plain strings in the database (not native Postgres enums),
so adding a value later is a code change, not a database migration.
"""

from enum import StrEnum


class Platform(StrEnum):
    BLUESKY = "bluesky"
    MASTODON = "mastodon"
    SAMPLE = "sample"  # hand-written demo posts, always labelled as such in the UI


class LifeEvent(StrEnum):
    NEW_BABY = "new_baby"
    HOME_PURCHASE = "home_purchase"
    BEREAVEMENT = "bereavement"
    NEW_BUSINESS = "new_business"
    MARRIAGE = "marriage"
    OTHER = "other"
    NONE = "none"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PostStatus(StrEnum):
    """Where a post is in the human review workflow."""

    NEW = "new"
    DRAFTED = "drafted"
    APPROVED = "approved"
    REPLIED = "replied"  # the user replied manually on the platform
    DISMISSED = "dismissed"


class Sensitivity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"  # grief, illness, financial distress: supportive tone only


class OutreachRecommendation(StrEnum):
    ENGAGE = "engage"
    SUPPORTIVE_ONLY = "supportive_only"  # reply with no product mention
    DO_NOT_CONTACT = "do_not_contact"


class DraftStatus(StrEnum):
    SUGGESTED = "suggested"
    APPROVED = "approved"
    REJECTED = "rejected"
