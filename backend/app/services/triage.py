"""AI triage: classify posts and recommend whether to reach out.

The model's answer is a recommendation. One safety rule is then enforced in
code: a highly sensitive post can never be marked "engage", whatever the
model says.
"""

import logging
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.ai.client import StructuredLLM
from app.ai.prompts import TRIAGE_SYSTEM, triage_user_message
from app.ai.schemas import PostTriage, TriageBatch
from app.db.enums import OutreachRecommendation, Sensitivity
from app.db.models import Post, PostAnalysis

logger = logging.getLogger(__name__)

BATCH_SIZE = 10  # posts per AI call: fewer calls, still small enough to be reliable


def apply_safety_rules(result: PostTriage) -> PostTriage:
    if (
        result.sensitivity == Sensitivity.HIGH
        and result.recommendation == OutreachRecommendation.ENGAGE
    ):
        return result.model_copy(update={"recommendation": OutreachRecommendation.SUPPORTIVE_ONLY})
    return result


def triage_posts(db: Session, posts: Sequence[Post], ai: StructuredLLM, model: str) -> int:
    """Analyse posts in batches and save the results. Returns how many were analysed."""
    analysed = 0
    for start in range(0, len(posts), BATCH_SIZE):
        batch = list(posts[start : start + BATCH_SIZE])
        response = ai.parse(
            model=model,
            system=TRIAGE_SYSTEM,
            user=triage_user_message(batch),
            schema=TriageBatch,
            effort="low",
            max_tokens=6000,
        )
        by_id = {post.id: post for post in batch}
        for result in response.results:
            post = by_id.pop(result.post_id, None)
            if post is None:
                continue  # the model returned an id we didn't send: ignore it
            _save(db, post, apply_safety_rules(result), model)
            analysed += 1
        if by_id:
            logger.warning("Triage skipped post ids %s", sorted(by_id))
        db.commit()
    return analysed


def _save(db: Session, post: Post, result: PostTriage, model: str) -> None:
    values = {
        "relevance": result.relevance,
        "life_event": result.life_event,
        "sensitivity": result.sensitivity,
        "recommendation": result.recommendation,
        "reason": result.reason,
        "summary": result.summary,
        "model": model,
    }
    if post.analysis is None:
        post.analysis = PostAnalysis(**values)
    else:  # re-analysis replaces the old result
        for field, value in values.items():
            setattr(post.analysis, field, value)
    db.flush()
