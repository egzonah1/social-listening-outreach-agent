"""Checks run in code on every draft, after the AI and after every human edit.

They don't block anything (a person always decides), but they show warnings
in the editor. Rules live in code, not just in the prompt, because a prompt
is a request and code is a guarantee.
"""

import re

from app.db.enums import OutreachRecommendation, Platform

CHAR_LIMITS: dict[Platform, int] = {
    Platform.BLUESKY: 300,
    Platform.MASTODON: 500,
    Platform.SAMPLE: 300,
}

PRESSURE_PHRASES = (
    "act now",
    "limited time",
    "don't miss",
    "dont miss",
    "guarantee",
    "best rate",
    "cheapest",
    "free quote",
    "get a quote",
    "sign up",
    "click here",
    "special offer",
    "discount",
)
INSURANCE_WORDS = ("insurance", "policy", "policies", "coverage", "cover you", "premium")
DISCLOSURE_PHRASES = ("i work in", "i work at", "i work with", "i'm an agent", "i am an agent")
URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)
MONEY_PATTERN = re.compile(r"[$€£]\s?\d|\d+\s?%")


def check_draft(
    text: str, platform: Platform, recommendation: OutreachRecommendation | None
) -> list[str]:
    warnings: list[str] = []
    lowered = text.lower()
    limit = CHAR_LIMITS.get(platform, 300)

    if not text.strip():
        warnings.append("The reply is empty.")
    if len(text) > limit:
        warnings.append(f"Too long for {platform.value}: {len(text)}/{limit} characters.")
    if any(phrase in lowered for phrase in PRESSURE_PHRASES):
        warnings.append("Contains sales-pressure language.")
    if URL_PATTERN.search(text):
        warnings.append("Contains a link. First replies should not include links.")
    if MONEY_PATTERN.search(text):
        warnings.append("Mentions prices or percentages.")

    mentions_insurance = any(word in lowered for word in INSURANCE_WORDS)
    if recommendation == OutreachRecommendation.DO_NOT_CONTACT:
        warnings.append("The AI recommended not contacting this person.")
    if recommendation == OutreachRecommendation.SUPPORTIVE_ONLY and mentions_insurance:
        warnings.append("This is a sensitive post: remove any mention of insurance.")
    if mentions_insurance and not any(p in lowered for p in DISCLOSURE_PHRASES):
        warnings.append("Mentions insurance without saying you work in it.")
    return warnings
