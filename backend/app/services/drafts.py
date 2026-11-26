"""Reply drafting and the human review workflow.

Every change is written to the audit log, so there is a record of what the
AI suggested, what a person changed, and who approved what.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.ai.client import StructuredLLM, model_used
from app.ai.guardrails import CHAR_LIMITS, check_draft
from app.ai.prompts import DRAFT_SYSTEM, draft_user_message
from app.ai.schemas import DraftSet
from app.db.enums import DraftStatus, PostStatus
from app.db.models import AuditEvent, Draft, Post


class WorkflowError(Exception):
    """An action that isn't allowed in the post's or draft's current state."""


def audit(db: Session, entity: Post | Draft, action: str, **details: Any) -> None:
    db.add(
        AuditEvent(
            entity_type="post" if isinstance(entity, Post) else "draft",
            entity_id=entity.id,
            action=action,
            details=details,
        )
    )


def generate_drafts(
    db: Session, post: Post, ai: StructuredLLM, model: str, instruction: str | None = None
) -> list[Draft]:
    limit = CHAR_LIMITS.get(post.platform, 300)
    result = ai.parse(
        model=model,
        system=DRAFT_SYSTEM,
        user=draft_user_message(post, post.analysis, limit, instruction),
        schema=DraftSet,
        effort="medium",
        max_tokens=4000,
    )
    used = model_used(ai, model)
    # Replace earlier suggestions that nobody approved; keep approved ones.
    for old in [d for d in post.drafts if d.status == DraftStatus.SUGGESTED]:
        post.drafts.remove(old)

    recommendation = post.analysis.recommendation if post.analysis else None
    new_drafts = [
        Draft(
            tone=variant.tone,
            text=variant.text.strip(),
            original_text=variant.text.strip(),
            model=used,
            warnings=check_draft(variant.text, post.platform, recommendation),
        )
        for variant in result.variants
    ]
    post.drafts.extend(new_drafts)
    if post.status == PostStatus.NEW:
        post.status = PostStatus.DRAFTED
    db.flush()
    audit(db, post, "drafts.generated", count=len(new_drafts), instruction=instruction)
    db.commit()
    return new_drafts


def edit_draft(db: Session, draft: Draft, text: str) -> Draft:
    if draft.status != DraftStatus.SUGGESTED:
        raise WorkflowError("Only drafts that are not yet approved or rejected can be edited.")
    recommendation = draft.post.analysis.recommendation if draft.post.analysis else None
    draft.text = text.strip()
    draft.warnings = check_draft(draft.text, draft.post.platform, recommendation)
    audit(db, draft, "draft.edited", length=len(draft.text))
    db.commit()
    return draft


def approve_draft(db: Session, draft: Draft) -> Draft:
    if draft.status != DraftStatus.SUGGESTED:
        raise WorkflowError("This draft has already been reviewed.")
    draft.status = DraftStatus.APPROVED
    draft.approved_at = datetime.now(UTC)
    draft.post.status = PostStatus.APPROVED
    audit(db, draft, "draft.approved", edited=draft.text != draft.original_text)
    db.commit()
    return draft


def reject_draft(db: Session, draft: Draft) -> Draft:
    if draft.status != DraftStatus.SUGGESTED:
        raise WorkflowError("This draft has already been reviewed.")
    draft.status = DraftStatus.REJECTED
    audit(db, draft, "draft.rejected")
    db.commit()
    return draft


def mark_replied(db: Session, post: Post) -> Post:
    """The user replied on the platform themselves. The app never posts anything."""
    if not any(d.status == DraftStatus.APPROVED for d in post.drafts):
        raise WorkflowError("Approve a draft before marking the post as replied.")
    post.status = PostStatus.REPLIED
    audit(db, post, "post.replied_manually")
    db.commit()
    return post


def dismiss_post(db: Session, post: Post) -> Post:
    post.status = PostStatus.DISMISSED
    audit(db, post, "post.dismissed")
    db.commit()
    return post
