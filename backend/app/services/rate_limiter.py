"""
Simple in-memory rate limiter.
In production, use Redis or similar for distributed rate limiting.
"""

import time
from collections import defaultdict
from threading import Lock


class RateLimiter:
    """
    Simple sliding window rate limiter.
    Tracks request counts per key within a time window.
    """

    def __init__(self, window_seconds: int = 60, max_requests: int = 10):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self._entries: dict[str, dict] = {}
        self._lock = Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """
        Check if a request is allowed for the given key.

        Returns:
            Tuple of (allowed, remaining_requests)
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            entry = self._entries.get(key)

            if not entry or entry["window_start"] < window_start:
                entry = {"window_start": now, "count": 0}

            entry["count"] += 1
            self._entries[key] = entry

            # Clean up old entries periodically
            if len(self._entries) > 100:
                self._cleanup(window_start)

            allowed = entry["count"] <= self.max_requests
            remaining = max(0, self.max_requests - entry["count"])

            return allowed, remaining

    def _cleanup(self, window_start: float):
        """Remove entries older than the current window."""
        keys_to_delete = [
            k for k, v in self._entries.items()
            if v["window_start"] < window_start
        ]
        for key in keys_to_delete:
            del self._entries[key]


# Global rate limiter instances
chat_limiter = RateLimiter(window_seconds=60, max_requests=10)
generate_limiter = RateLimiter(window_seconds=60, max_requests=5)
