"""In-memory sliding-window throttling for the authentication endpoint.

Blocks brute-force password guessing: after `limit` failed sign-in attempts
for the same (client, email) pair inside `window_seconds`, further attempts
receive HTTP 429 until the window slides. Successful sign-ins reset the
counter. Swap for Redis in a multi-instance deployment.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class LoginThrottle:
    def __init__(self, limit: int = 5, window_seconds: int = 900) -> None:
        self.limit = limit
        self.window = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @staticmethod
    def _key(request: Request, email: str) -> str:
        client = request.client.host if request.client else "unknown"
        return f"{client}:{email.strip().lower()}"

    def check(self, request: Request, email: str) -> None:
        """Raise 429 if the (client, email) pair is out of attempts."""
        now = time.monotonic()
        with self._lock:
            window = self._failures[self._key(request, email)]
            while window and now - window[0] > self.window:
                window.popleft()
            if len(window) >= self.limit:
                raise HTTPException(
                    status_code=429,
                    detail="Too many failed sign-in attempts. Please try again in a few minutes.",
                )

    def record_failure(self, request: Request, email: str) -> None:
        with self._lock:
            self._failures[self._key(request, email)].append(time.monotonic())

    def reset(self, request: Request, email: str) -> None:
        with self._lock:
            self._failures.pop(self._key(request, email), None)


login_throttle = LoginThrottle()
