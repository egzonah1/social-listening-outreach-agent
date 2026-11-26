"""The no-AI backup: keyword triage, template drafts, and falling back when the AI fails."""

import json

import pytest
from sqlalchemy.orm import Session

from app.ai.client import AIError
from app.ai.factory import build_ai_client
from app.ai.gemini import GeminiClient
from app.ai.guardrails import check_draft
from app.ai.rules import FallbackLLM, RuleBasedLLM, triage_one
from app.ai.schemas import DraftSet, PostTriage, TriageBatch
from app.core.config import Settings
from app.db.enums import LifeEvent, OutreachRecommendation, Platform, Sensitivity
from app.services.drafts import generate_drafts
from app.services.triage import triage_posts
from tests.fakes import FakeLLM
from tests.test_triage import make_posts

Rec = OutreachRecommendation


@pytest.mark.parametrize(
    ("text", "event", "recommendation", "sensitivity"),
    [
        (
            "Our baby arrived this morning, we're over the moon",
            LifeEvent.NEW_BABY,
            Rec.ENGAGE,
            Sensitivity.LOW,
        ),
        (
            "We finally got the keys to our first home!",
            LifeEvent.HOME_PURCHASE,
            Rec.ENGAGE,
            Sensitivity.MEDIUM,
        ),
        (
            "My dad passed away yesterday.",
            LifeEvent.BEREAVEMENT,
            Rec.DO_NOT_CONTACT,
            Sensitivity.HIGH,
        ),
        (
            "A year since my mom passed away. Still miss her.",
            LifeEvent.BEREAVEMENT,
            Rec.SUPPORTIVE_ONLY,
            Sensitivity.HIGH,
        ),
        (
            "Our son was stillborn last month.",
            LifeEvent.BEREAVEMENT,
            Rec.DO_NOT_CONTACT,
            Sensitivity.HIGH,
        ),
        (
            "New baby and I just got laid off. Scared.",
            LifeEvent.NEW_BABY,
            Rec.SUPPORTIVE_ONLY,
            Sensitivity.HIGH,
        ),
        (
            "Newborn photo shoots 20% off, link in bio",
            LifeEvent.NEW_BABY,
            Rec.DO_NOT_CONTACT,
            Sensitivity.LOW,
        ),
        ("Lovely weather in the park.", LifeEvent.NONE, Rec.DO_NOT_CONTACT, Sensitivity.LOW),
    ],
)
def test_keyword_triage(
    text: str, event: LifeEvent, recommendation: Rec, sensitivity: Sensitivity
) -> None:
    result = triage_one(1, text)

    assert (result.life_event, result.recommendation, result.sensitivity) == (
        event,
        recommendation,
        sensitivity,
    )
    assert result.reason.startswith("Backup rules")


def test_rules_triage_and_drafts_are_saved_as_rules(db: Session) -> None:
    posts = make_posts(db, 2)  # "Our baby arrived ..."

    assert triage_posts(db, posts, RuleBasedLLM(), model="gemini-test") == 2
    drafts = generate_drafts(db, posts[0], RuleBasedLLM(), model="gemini-test")

    assert posts[0].analysis and posts[0].analysis.model == "rules"
    assert posts[0].analysis.recommendation == Rec.ENGAGE
    assert [d.tone for d in drafts] == ["warm", "helpful", "brief"]
    assert all(d.model == "rules" for d in drafts)
    assert all(d.warnings == [] for d in drafts)  # templates pass the guardrails


def test_supportive_drafts_never_mention_insurance() -> None:
    user = (
        "Platform: bluesky (character limit: 300)\nRecommendation: supportive_only\n"
        "Detected life event: bereavement\nSensitivity: high\n<post>...</post>"
    )
    result = RuleBasedLLM().parse(model="rules", system="", user=user, schema=DraftSet)

    for variant in result.variants:
        assert check_draft(variant.text, Platform.BLUESKY, Rec.SUPPORTIVE_ONLY) == []
        assert "insurance" not in variant.text.lower()


def test_fallback_uses_rules_when_ai_fails(db: Session) -> None:
    posts = make_posts(db, 1)
    failing = FakeLLM(responder=lambda **_: TriageBatch(results=[]))
    failing.error = AIError("The AI free-tier limit was reached.")
    ai = FallbackLLM(failing)

    triage_posts(db, posts, ai, model="gemini-test")

    assert posts[0].analysis and posts[0].analysis.model == "rules"


def test_fallback_keeps_ai_answer_when_ai_works(db: Session) -> None:
    posts = make_posts(db, 1)

    def respond(schema: type, user: str) -> TriageBatch:
        post_id = json.loads(user.split("<posts>\n")[1].split("\n</posts>")[0])[0]["post_id"]
        return TriageBatch(
            results=[
                PostTriage(
                    post_id=post_id,
                    relevance=90,
                    life_event=LifeEvent.NEW_BABY,
                    sensitivity=Sensitivity.LOW,
                    recommendation=Rec.ENGAGE,
                    reason="r",
                    summary="s",
                )
            ]
        )

    triage_posts(db, posts, FallbackLLM(FakeLLM(responder=respond)), model="gemini-test")

    assert posts[0].analysis and posts[0].analysis.model == "gemini-test"


def test_factory_picks_provider_from_settings() -> None:
    with_key = build_ai_client(Settings(_env_file=None, gemini_api_key="k"))
    no_fallback = build_ai_client(
        Settings(_env_file=None, gemini_api_key="k", ai_fallback_to_rules=False)
    )
    no_key = build_ai_client(Settings(_env_file=None))
    off = build_ai_client(Settings(_env_file=None, ai_fallback_to_rules=False))

    assert isinstance(with_key, FallbackLLM)
    assert isinstance(no_fallback, GeminiClient)
    assert isinstance(no_key, RuleBasedLLM)
    assert off is None
