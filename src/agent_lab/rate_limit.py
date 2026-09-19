"""Small deterministic fixed-window rate limiter for the API boundary."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class _Window:
    started_at: float
    count: int = 0


class FixedWindowRateLimiter:
    def __init__(self, *, max_requests: int = 60, window_seconds: float = 60.0) -> None:
        if max_requests <= 0 or window_seconds <= 0:
            raise ValueError("rate limit and window must be positive")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[str, _Window] = {}

    def allow(self, key: str, *, now: float | None = None) -> tuple[bool, int]:
        current = time.monotonic() if now is None else now
        window = self._windows.get(key)
        if window is None or current - window.started_at >= self.window_seconds:
            window = _Window(current, 0)
            self._windows[key] = window
        if window.count >= self.max_requests:
            retry_after = max(1, int(self.window_seconds - (current - window.started_at) + 0.999))
            return False, retry_after
        window.count += 1
        return True, 0

    def snapshot(self) -> dict[str, int]:
        return {"keys": len(self._windows), "max_requests": self.max_requests}
