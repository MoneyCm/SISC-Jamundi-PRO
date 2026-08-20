"""
In-memory rate limiter with TTL.
Limitations: resets on instance restart, not global across multiple workers.
Interface prepared for Redis (get/set methods abstracted).
Configurable via environment variables.
"""

import os
import time
from collections import defaultdict
from typing import Optional

from fastapi import Request, HTTPException


_RATE_LIMIT_EXPLORE = int(os.getenv("SISC_RATE_LIMIT_EXPLORE", "60"))
_RATE_LIMIT_GENERAL = int(os.getenv("SISC_RATE_LIMIT_GENERAL", "300"))
_RATE_LIMIT_WINDOW = int(os.getenv("SISC_RATE_LIMIT_WINDOW_SECONDS", "60"))
_RATE_LIMIT_IP_STRATEGY = os.getenv("SISC_RATE_LIMIT_IP_STRATEGY", "forwarded_last")


class RateLimitStore:
    def __init__(self) -> None:
        self._store: dict[str, list[float]] = defaultdict(list)

    def get(self, key: str) -> list[float]:
        now = time.time()
        cutoff = now - _RATE_LIMIT_WINDOW
        self._store[key] = [t for t in self._store[key] if t > cutoff]
        return self._store[key]

    def add(self, key: str) -> list[float]:
        now = time.time()
        cutoff = now - _RATE_LIMIT_WINDOW
        self._store[key] = [t for t in self._store[key] if t > cutoff]
        self._store[key].append(now)
        return self._store[key]

    def remaining(self, key: str, limit: int) -> int:
        return max(0, limit - len(self.get(key)))


_store = RateLimitStore()


def get_client_ip(request: Request) -> str:
    """
    Extract client IP from a trusted proxy chain.

    Strategy (configurable via SISC_RATE_LIMIT_IP_STRATEGY):
    - "forwarded_last": last value in X-Forwarded-For (most reliable behind
      known reverse proxies like Render, Cloudflare, Nginx that append).
    - "forwarded_first": first value (legacy behavior, spoofable).
    - "client": always use request.client.host (bypasses proxy headers).
    """
    strategy = _RATE_LIMIT_IP_STRATEGY

    if strategy == "client":
        if request.client:
            return request.client.host
        return "unknown"

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            if strategy == "forwarded_last":
                return parts[-1]
            return parts[0]

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    if request.client:
        return request.client.host
    return "unknown"


def check_rate_limit(request: Request, limit: int = _RATE_LIMIT_GENERAL) -> None:
    ip = get_client_ip(request)
    timestamps = _store.add(f"ip:{ip}")
    if len(timestamps) > limit:
        raise HTTPException(
            status_code=429,
            detail={
                "schema_version": "1.0",
                "status": "error",
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": f"Límite de {limit} requests por {_RATE_LIMIT_WINDOW}s excedido.",
            },
        )


def rate_limit_explore(request: Request) -> None:
    check_rate_limit(request, limit=_RATE_LIMIT_EXPLORE)


def rate_limit_general(request: Request) -> None:
    check_rate_limit(request, limit=_RATE_LIMIT_GENERAL)


def get_rate_limit_info() -> dict:
    return {
        "requests_per_minute": _RATE_LIMIT_EXPLORE,
        "burst": _RATE_LIMIT_EXPLORE,
    }
