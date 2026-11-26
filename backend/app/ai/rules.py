"""A backup that works without any AI service: keyword rules and reply templates.

It implements the same `parse()` interface as the AI clients, so the services
don't know the difference. It is used when AI_PROVIDER=rules, or by
`FallbackLLM` when the AI fails (for example when the free daily limit is used
up), so a demo never stops working.

It is deliberately cautious and much less smart than a model: it only reads
English keywords, can't tell a joke from a real event, and its replies are
generic. Results are saved with the model name "rules" and every reason says
so, so a person always knows a rule (not an AI) made the call.
"""

import json
import logging
import re
from typing import TypeVar, cast

from pydantic import BaseModel

from app.ai.client import AIError, Effort, StructuredLLM
from app.ai.schemas import DraftSet, DraftVariant, PostTriage, TriageBatch
from app.core.config import RULES_MODEL
from app.db.enums import LifeEvent, OutreachRecommendation, Sensitivity

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

LABEL = "Backup rules (AI unavailable)"

EVENT_KEYWORDS: dict[LifeEvent, tuple[str, ...]] = {
    LifeEvent.BEREAVEMENT: (
        "passed away",
        "funeral",
        "rest in peace",
        "grieving",
        "lost my mom",
        "lost my dad",
        "lost my mother",
        "lost my father",
        "lost my husband",
        "lost my wife",
        "lost my mum",
        "since we lost",
        "father's estate",
        "mother's estate",
        "miscarriage",
        "stillborn",
        "lost our baby",
        "in loving memory",
    ),
    LifeEvent.NEW_BABY: (
        "new baby",
        "baby arrived",
        "baby is here",
        "welcomed our",
        "newborn",
        "baby girl",
        "baby boy",
        "we're expecting",
        "we are expecting",
        "i'm pregnant",
        "first-time parent",
        "first time parent",
        "became a dad",
        "became a mom",
        "baby number",
        "baby on the way",
        "first baby",
        "brought our daughter home",
        "brought our son home",
        "twins due",
        "pregnant",
        "maternity leave",
        "paternity leave",
    ),
    LifeEvent.HOME_PURCHASE: (
        "bought a house",
        "bought our first",
        "first home",
        "new home",
        "new house",
        "closed on",
        "got the keys",
        "homeowner",
        "mortgage",
        "first house",
        "closing on our",
        "moved into our",
        "house hunting",
    ),
    LifeEvent.NEW_BUSINESS: (
        "started my own business",
        "started my business",
        "launched my business",
        "opened my own",
        "my new business",
        "small business owner",
        "quit my job to start",
        "registered my own",
        "running my own",
        "my own business",
        "freelance business",
        "started my freelance",
        "our bakery",
        "our cafe",
        "our shop",
        "our restaurant",
    ),
    LifeEvent.MARRIAGE: (
        "got married",
        "just married",
        "we're engaged",
        "we got engaged",
        "our wedding",
        "newlyweds",
        "she said yes",
        "he said yes",
        "he proposed",
        "she proposed",
        "#engaged",
        "married the love",
    ),
}
# Checked in this order, so grief always wins over a happier keyword.
EVENT_ORDER = [
    LifeEvent.BEREAVEMENT,
    LifeEvent.NEW_BABY,
    LifeEvent.HOME_PURCHASE,
    LifeEvent.NEW_BUSINESS,
    LifeEvent.MARRIAGE,
]
DISTRESS = (
    "divorce",
    "laid off",
    "lost my job",
    "diagnosed",
    "cancer",
    "in hospital",
    "chemo",
    "bankrupt",
)
# Losing a baby is always "do not contact", as the AI prompt also says.
BABY_LOSS = ("stillborn", "miscarriage", "lost our baby")
RECENT = ("today", "yesterday", "last night", "this morning", "this week")
SPAM = (
    "http",
    "www.",
    "discount",
    "promo",
    "sale",
    "buy now",
    "dm me",
    "#ad",
    "sponsored",
    "link in bio",
    "follow for",
    "giveaway",
    "dm us",
    "limited time",
    "new listing",
    "my course",
)
PERSONAL = re.compile(r"\b(i|i'm|i've|we|we're|we've|my|our|us)\b", re.IGNORECASE)

EVENT_WORDS: dict[LifeEvent, str] = {
    LifeEvent.NEW_BABY: "the new baby",
    LifeEvent.HOME_PURCHASE: "the new home",
    LifeEvent.NEW_BUSINESS: "the new business",
    LifeEvent.MARRIAGE: "the wedding",
}
SUPPORTIVE = {
    "warm": "I'm so sorry you're going through this. Sending you strength and kind thoughts.",
    "helpful": "I'm really sorry. Please be gentle with yourself, and I hope you have people "
    "around you right now.",
    "brief": "So sorry to hear this. Thinking of you.",
}


class RuleBasedLLM:
    """Answers triage and drafting requests with keyword rules instead of a model."""

    # Read by `model_used()`: results are always saved as made by "rules".
    last_model_used = RULES_MODEL

    def parse(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: type[T],
        effort: Effort = "medium",
        max_tokens: int = 4000,
    ) -> T:
        if schema is TriageBatch:
            return cast(T, triage(user))
        if schema is DraftSet:
            return cast(T, drafts(user))
        raise AIError(f"The backup rules can't produce {schema.__name__}.")


class FallbackLLM:
    """Tries the AI first and uses the rules if the AI call fails."""

    def __init__(self, primary: StructuredLLM, backup: StructuredLLM | None = None) -> None:
        self._primary = primary
        self._backup = backup or RuleBasedLLM()
        # Read by `model_used()` so results are saved with the name of what produced them.
        self.last_model_used: str | None = None

    def parse(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: type[T],
        effort: Effort = "medium",
        max_tokens: int = 4000,
    ) -> T:
        try:
            result = self._primary.parse(
                model=model,
                system=system,
                user=user,
                schema=schema,
                effort=effort,
                max_tokens=max_tokens,
            )
            self.last_model_used = model
        except AIError as exc:
            logger.warning("AI call failed (%s); using the backup rules instead.", exc)
            result = self._backup.parse(
                model=RULES_MODEL,
                system=system,
                user=user,
                schema=schema,
                effort=effort,
                max_tokens=max_tokens,
            )
            self.last_model_used = RULES_MODEL
        return result


# ---- triage -----------------------------------------------------------------


def triage(user: str) -> TriageBatch:
    match = re.search(r"<posts>\n(.*)\n</posts>", user, re.S)
    if match is None:
        raise AIError("The backup rules could not read the posts.")
    posts = json.loads(match.group(1))
    return TriageBatch(results=[triage_one(p["post_id"], p["text"]) for p in posts])


def triage_one(post_id: int, text: str) -> PostTriage:
    lowered = text.lower()
    event, keyword = _find_event(lowered)
    personal = bool(PERSONAL.search(text))
    spam = next((word for word in SPAM if word in lowered), None)
    distress = any(word in lowered for word in DISTRESS)

    def result(
        relevance: int, sensitivity: Sensitivity, rec: OutreachRecommendation, reason: str
    ) -> PostTriage:
        summary = (
            f"Mentions {keyword!r} (keyword match)." if keyword else "No life event keyword found."
        )
        return PostTriage(
            post_id=post_id,
            relevance=relevance,
            life_event=event,
            sensitivity=sensitivity,
            recommendation=rec,
            reason=f"{LABEL}: {reason}",
            summary=summary,
        )

    if spam:
        return result(
            5,
            Sensitivity.LOW,
            OutreachRecommendation.DO_NOT_CONTACT,
            f"looks like an ad or promotion ({spam!r}).",
        )
    if event == LifeEvent.NONE:
        return result(
            5,
            Sensitivity.LOW,
            OutreachRecommendation.DO_NOT_CONTACT,
            "no personal life event found.",
        )
    if not personal:
        return result(
            20,
            Sensitivity.LOW,
            OutreachRecommendation.DO_NOT_CONTACT,
            f"mentions {keyword!r} but doesn't read like the author's own news.",
        )
    if event == LifeEvent.BEREAVEMENT:
        recent = any(word in lowered for word in RECENT + BABY_LOSS)
        rec = (
            OutreachRecommendation.DO_NOT_CONTACT
            if recent
            else OutreachRecommendation.SUPPORTIVE_ONLY
        )
        why = (
            "a very recent loss or a baby loss: leave them be."
            if recent
            else "a loss: kindness only."
        )
        return result(60, Sensitivity.HIGH, rec, why)
    if distress:
        return result(
            50,
            Sensitivity.HIGH,
            OutreachRecommendation.SUPPORTIVE_ONLY,
            f"mentions {keyword!r} together with illness or money worries.",
        )
    sensitivity = (
        Sensitivity.MEDIUM
        if event in (LifeEvent.HOME_PURCHASE, LifeEvent.NEW_BUSINESS)
        else Sensitivity.LOW
    )
    return result(
        65,
        sensitivity,
        OutreachRecommendation.ENGAGE,
        f"the author mentions {keyword!r} about their own life.",
    )


def _find_event(lowered: str) -> tuple[LifeEvent, str | None]:
    for event in EVENT_ORDER:
        for keyword in EVENT_KEYWORDS[event]:
            if keyword in lowered:
                return event, keyword
    return LifeEvent.NONE, None


# ---- drafts -----------------------------------------------------------------


def drafts(user: str) -> DraftSet:
    limit = int(_field(user, r"character limit: (\d+)") or 300)
    recommendation = _field(user, r"^Recommendation: (\w+)$")
    event = _field(user, r"^Detected life event: (\w+)$")

    if recommendation != OutreachRecommendation.ENGAGE.value or event not in EVENT_WORDS:
        texts = SUPPORTIVE
    else:
        thing = EVENT_WORDS[LifeEvent(event)]
        texts = {
            "warm": f"Congratulations on {thing}! Wishing you lots of happy moments ahead.",
            "helpful": f"Congratulations on {thing}! I work in life insurance, so if questions "
            "about protecting your family ever come up, I'm happy to help. No pressure at all.",
            "brief": f"Congrats on {thing}!",
        }
    return DraftSet(
        variants=[DraftVariant(tone=tone, text=text[:limit]) for tone, text in texts.items()]
    )


def _field(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1) if match else None
