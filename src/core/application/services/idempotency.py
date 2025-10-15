import hashlib
import os
import time
from typing import Optional

import redis


def compute_idempotency_key(sha256: str, size: int, mime: Optional[str], tenant_id: str = "default") -> str:
    base = f"{tenant_id}|{sha256}|{size}|{mime or ''}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


class InflightGuard:
    def __init__(self, ttl_seconds: int = 600) -> None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._r = redis.Redis.from_url(url)
        self._ttl = ttl_seconds

    def acquire(self, key: str) -> bool:
        # Use SET NX EX for atomic lock with TTL
        return bool(self._r.set(name=f"idem:lock:{key}", value=int(time.time()), nx=True, ex=self._ttl))

    def release(self, key: str) -> None:
        try:
            self._r.delete(f"idem:lock:{key}")
        except Exception:
            pass
