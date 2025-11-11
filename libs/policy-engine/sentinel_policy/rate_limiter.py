"""Rate limiting implementation for policy engine."""

import time
from collections import defaultdict
from threading import Lock
from typing import Any


class RateLimiter:
    """
    In-memory rate limiter with sliding window algorithm.

    Tracks operation counts within time windows to enforce rate limits.
    Thread-safe for concurrent access.

    Note: For production use with multiple instances, use Redis-based
    rate limiting instead of this in-memory implementation.
    """

    def __init__(self):
        """Initialize rate limiter."""
        # Store: {resource_key: [(timestamp, count), ...]}
        self._windows: dict[str, list[tuple[float, int]]] = defaultdict(list)
        self._lock = Lock()

    def check_rate_limit(
        self,
        resource_key: str,
        max_operations: int,
        window_seconds: int,
        increment: int = 1,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Check if operation is within rate limit.

        Args:
            resource_key: Unique identifier for the resource being rate limited
            max_operations: Maximum number of operations allowed in the window
            window_seconds: Time window in seconds
            increment: Number of operations to add (default: 1)

        Returns:
            Tuple of (allowed: bool, metadata: dict)
            - allowed: True if within rate limit
            - metadata: Dict with current_count, limit, window_end_time
        """
        with self._lock:
            current_time = time.time()
            window_start = current_time - window_seconds

            # Get or create window for this resource
            windows = self._windows[resource_key]

            # Remove expired entries (older than window_start)
            windows[:] = [(ts, count) for ts, count in windows if ts >= window_start]

            # Calculate current count within window
            current_count = sum(count for _, count in windows)

            # Check if adding increment would exceed limit
            new_count = current_count + increment
            allowed = new_count <= max_operations

            if allowed:
                # Add new entry
                windows.append((current_time, increment))

            metadata = {
                "current_count": current_count,
                "limit": max_operations,
                "window_seconds": window_seconds,
                "window_end_time": current_time + window_seconds,
                "remaining": max(0, max_operations - new_count),
            }

            return allowed, metadata

    def get_current_count(self, resource_key: str, window_seconds: int) -> int:
        """
        Get current operation count for a resource within the window.

        Args:
            resource_key: Resource identifier
            window_seconds: Time window in seconds

        Returns:
            Current operation count
        """
        with self._lock:
            current_time = time.time()
            window_start = current_time - window_seconds

            windows = self._windows.get(resource_key, [])
            windows[:] = [(ts, count) for ts, count in windows if ts >= window_start]

            return sum(count for _, count in windows)

    def reset(self, resource_key: str | None = None) -> None:
        """
        Reset rate limit counters.

        Args:
            resource_key: If provided, reset only this resource. Otherwise reset all.
        """
        with self._lock:
            if resource_key:
                self._windows.pop(resource_key, None)
            else:
                self._windows.clear()

    def cleanup_expired(self, max_age_seconds: int = 3600) -> int:
        """
        Clean up very old entries to prevent memory growth.

        Args:
            max_age_seconds: Remove entries older than this (default: 1 hour)

        Returns:
            Number of entries removed
        """
        with self._lock:
            current_time = time.time()
            cutoff_time = current_time - max_age_seconds
            removed_count = 0

            for resource_key in list(self._windows.keys()):
                windows = self._windows[resource_key]
                original_len = len(windows)
                windows[:] = [(ts, count) for ts, count in windows if ts >= cutoff_time]
                removed_count += original_len - len(windows)

                # Remove empty lists
                if not windows:
                    del self._windows[resource_key]

            return removed_count
