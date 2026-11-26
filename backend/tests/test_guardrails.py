from app.ai.guardrails import check_draft
from app.db.enums import OutreachRecommendation, Platform

ENGAGE = OutreachRecommendation.ENGAGE
SUPPORTIVE = OutreachRecommendation.SUPPORTIVE_ONLY


def test_good_reply_has_no_warnings() -> None:
    text = "Congratulations on your daughter! The first weeks are a blur, sleep when you can."
    assert check_draft(text, Platform.BLUESKY, ENGAGE) == []


def test_too_long_for_bluesky() -> None:
    warnings = check_draft("a" * 301, Platform.BLUESKY, ENGAGE)
    assert any("Too long" in w for w in warnings)
    assert check_draft("a" * 301, Platform.MASTODON, ENGAGE) == []


def test_sales_pressure_links_and_prices_are_flagged() -> None:
    warnings = check_draft(
        "Act now! I work in insurance, get 20% off at https://example.com",
        Platform.BLUESKY,
        ENGAGE,
    )
    assert len(warnings) == 3


def test_insurance_without_disclosure_is_flagged() -> None:
    hidden = check_draft("Have you thought about life insurance?", Platform.BLUESKY, ENGAGE)
    open_ = check_draft(
        "I work in life insurance, happy to answer questions.", Platform.BLUESKY, ENGAGE
    )
    assert any("without saying" in w for w in hidden)
    assert open_ == []


def test_sensitive_post_must_not_mention_insurance() -> None:
    warnings = check_draft(
        "I work in insurance and I'm so sorry for your loss.", Platform.BLUESKY, SUPPORTIVE
    )
    assert any("sensitive" in w for w in warnings)
