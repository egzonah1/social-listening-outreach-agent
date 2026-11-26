"""Simple in-memory rate limits.

The live demo runs on free tiers (Gemini's daily quota, one small Render
instance), so a stranger with the link must not be able to use it all up.
Each limit counts events in a sliding time window, per client and in total.

In memory is enough here: the app runs as one process. With several
instances this would move to Redis or Postgres.
"""

import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class Limit:
    name: str
    max_events: int
    window_seconds: float

    @property
    def enabled(self) -> bool:
        return self.max_events > 0


class RateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def hit(self, limit: Limit, key: str) -> float | None:
        """Record one event. Returns None if allowed, else seconds until a slot frees up."""
        if not limit.enabled:
            return None
        now = self._clock()
        with self._lock:
            events = self._events[(limit.name, key)]
            while events and events[0] <= now - limit.window_seconds:
                events.popleft()
            if len(events) >= limit.max_events:
                return max(1.0, events[0] + limit.window_seconds - now)
            events.append(now)
            return None
