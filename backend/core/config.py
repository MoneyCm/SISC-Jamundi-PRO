import os
from typing import Iterable, List, Optional


DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://sisc-frontend.onrender.com",
)

WEAK_SECRET_MARKERS = (
    "change_me",
    "change-me",
    "replace_with",
    "super_secret",
    "use_a_random",
    "development",
)

WEAK_SECRET_MARKERS = (
    "change_me",
    "change-me",
    "replace_with",
    "super_secret",
    "use_a_random",
    "development",
)


def get_cors_origins(raw_origins: Optional[str] = None) -> List[str]:
    raw = os.getenv("CORS_ORIGINS", "") if raw_origins is None else raw_origins
    candidates: Iterable[str] = raw.split(",") if raw.strip() else DEFAULT_CORS_ORIGINS
    origins = list(dict.fromkeys(origin.strip().rstrip("/") for origin in candidates if origin.strip()))
    if "*" in origins:
        raise RuntimeError("CORS_ORIGINS no puede contener '*' en SISC.")
    return origins


def is_strong_secret(value: Optional[str], minimum_length: int = 32) -> bool:
    candidate = (value or "").strip()
    normalized = candidate.lower()
    return len(candidate) >= minimum_length and not any(
        marker in normalized for marker in WEAK_SECRET_MARKERS
    )


def is_strong_secret(value: Optional[str], minimum_length: int = 32) -> bool:
    candidate = (value or "").strip()
    normalized = candidate.lower()
    return len(candidate) >= minimum_length and not any(
        marker in normalized for marker in WEAK_SECRET_MARKERS
    )
