"""In-memory async cache and request pacing utilities."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Generic, TypeVar
import asyncio

T = TypeVar("T")


@dataclass(slots=True)
class _CacheEntry(Generic[T]):
    value: T
    expires_at: float


class AsyncTTLCache(Generic[T]):
    """Simple async-safe TTL cache."""

    def __init__(self) -> None:
        self._store: dict[str, _CacheEntry[T]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> T | None:
        now = time.monotonic()
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                del self._store[key]
                return None
            return entry.value

    async def set(self, key: str, value: T, ttl_seconds: int) -> None:
        expires_at = time.monotonic() + ttl_seconds
        async with self._lock:
            self._store[key] = _CacheEntry(value=value, expires_at=expires_at)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()


class SimpleRateLimiter:
    """Ensures a minimum interval between outbound requests."""

    def __init__(self, min_interval_seconds: float) -> None:
        self._min_interval = min_interval_seconds
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0

    async def wait_turn(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_at
            remaining = self._min_interval - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)
            self._last_request_at = time.monotonic()
