"""Export approved replies as CSV, so a team can work through them or keep a record.

Only what is needed to send the reply by hand is exported: the link to the
post, the author's handle and the approved text. The person's own post text is
left out on purpose (data minimisation): the link opens it at the source.
"""

import csv
import io
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.enums import DraftStatus
from app.db.models import AuditEvent, Campaign, Draft, Post

COLUMNS = [
    "post_url",
    "platform",
    "author_handle",
    "life_event",
    "reply_tone",
    "approved_reply",
    "approved_at",
    "post_status",
]
# Spreadsheet apps run cells that start with these as formulas ("CSV injection").
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: str) -> str:
    return f"'{value}" if value.startswith(FORMULA_START) else value


def approved_replies_csv(db: Session, campaign: Campaign) -> tuple[str, int]:
    """Return the CSV text and how many replies it holds."""
    drafts = db.scalars(
        select(Draft)
        .join(Post)
        .where(Post.campaign_id == campaign.id, Draft.status == DraftStatus.APPROVED)
        .options(selectinload(Draft.post).selectinload(Post.analysis))
        .order_by(Draft.approved_at.desc().nulls_last(), Draft.id.desc())
    ).all()

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(COLUMNS)
    for draft in drafts:
        post = draft.post
        writer.writerow(
            [
                safe_cell(post.url),
                post.platform.value,
                safe_cell(post.author_handle),
                post.analysis.life_event.value if post.analysis else "",
                draft.tone,
                safe_cell(draft.text),
                _iso(draft.approved_at),
                post.status.value,
            ]
        )
    db.add(
        AuditEvent(
            entity_type="campaign",
            entity_id=campaign.id,
            action="campaign.exported",
            details={"replies": len(drafts)},
        )
    )
    db.commit()
    return out.getvalue(), len(drafts)


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else ""
