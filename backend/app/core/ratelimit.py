"""Failure counters for throttling. Redis when REDIS_URL is set (shared across workers), else in-memory."""
import logging
import time
from collections import defaultdict

log = logging.getLogger("ratelimit")


class MemoryCounter:
    def __init__(self):
        self._hits: dict[str, list[float]] = defaultdict(list)

    def count(self, key: str, window: int) -> int:
        now = time.time()
        self._hits[key] = [t for t in self._hits[key] if now - t < window]
        return len(self._hits[key])

    def incr(self, key: str, window: int) -> None:
        self.count(key, window)
        self._hits[key].append(time.time())

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)


class RedisCounter:
    """Fixed-window counter. Fails open on Redis errors so an outage can't lock everyone out."""

    def __init__(self, url: str):
        import redis  # lazy: only needed when REDIS_URL is configured
        self._r = redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)

    def count(self, key: str, window: int) -> int:
        try:
            return int(self._r.get("rl:" + key) or 0)
        except Exception as e:
            log.warning("redis unavailable: %r", e)
            return 0

    def incr(self, key: str, window: int) -> None:
        try:
            pipe = self._r.pipeline()
            pipe.incr("rl:" + key)
            pipe.expire("rl:" + key, window, nx=True)
            pipe.execute()
        except Exception as e:
            log.warning("redis unavailable: %r", e)

    def reset(self, key: str) -> None:
        try:
            self._r.delete("rl:" + key)
        except Exception as e:
            log.warning("redis unavailable: %r", e)


def build_counter(redis_url: str):
    return RedisCounter(redis_url) if redis_url else MemoryCounter()
