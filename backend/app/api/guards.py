"""Protection for the public demo: an access code and usage limits.

- Access code: when ACCESS_CODE is set, every API call except /api/health and
  /api/meta must send it in the X-Access-Code header. The reviewers get the
  code with the link, so the public internet can't use the tool.
- Usage limits: searches and AI calls are limited per client (IP address)
  and in total, so nobody can burn through the free AI quota.
"""

import hmac
import math
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.core.limits import Limit, RateLimiter

DAY = 24 * 3600
HOUR = 3600

# Wrong codes per client per 15 minutes, so the code can't be guessed by brute force.
WRONG_CODE_LIMIT = Limit("wrong_code", 10, 15 * 60)


def client_key(request: Request) -> str:
    # Uvicorn runs with --proxy-headers on Render, so this is the visitor's IP.
    return request.client.host if request.client else "unknown"


def _limiter(request: Request) -> RateLimiter:
    limiter: RateLimiter = request.app.state.limiter
    return limiter


def _too_many(retry_after: float, message: str) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        message,
        headers={"Retry-After": str(math.ceil(retry_after))},
    )


def require_access_code(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    x_access_code: Annotated[str | None, Header()] = None,
) -> None:
    expected = settings.access_code.get_secret_value() if settings.access_code else ""
    if not expected:
        return
    # compare_digest takes the same time for any wrong code (no timing hints).
    if x_access_code and hmac.compare_digest(x_access_code.encode(), expected.encode()):
        return
    if x_access_code:
        wait = _limiter(request).hit(WRONG_CODE_LIMIT, client_key(request))
        if wait is not None:
            raise _too_many(wait, "Too many wrong access codes. Try again later.")
    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Access code required" if not x_access_code else "Wrong access code",
    )


def _check(request: Request, per_client: Limit, total: Limit, what: str) -> None:
    limiter = _limiter(request)
    wait = limiter.hit(per_client, client_key(request))
    if wait is not None:
        raise _too_many(wait, f"Limit reached: {what}. Try again in {math.ceil(wait / 60)} min.")
    wait = limiter.hit(total, "all")
    if wait is not None:
        raise _too_many(wait, f"The demo's daily limit for {what} is used up. Try again later.")


def limit_searches(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    _check(
        request,
        Limit("searches", settings.searches_per_hour, HOUR),
        Limit("searches_total", settings.searches_per_day_total, DAY),
        "searches",
    )


def limit_ai(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    _check(
        request,
        Limit("ai", settings.ai_actions_per_hour, HOUR),
        Limit("ai_total", settings.ai_actions_per_day_total, DAY),
        "AI actions",
    )
