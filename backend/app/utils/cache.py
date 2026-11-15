"""Tiny JSON file cache under data/cache/ (gitignored). Keeps live NASA and partner-service pulls fast and polite."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from app.config import settings


def _path(namespace: str, key: str) -> Path:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
    return settings.cache_dir / f"{namespace}-{digest}.json"


def get(namespace: str, key: str, ttl_hours: float | None = None) -> Any | None:
    """Return the cached payload, or None when missing or older than the TTL."""
    path = _path(namespace, key)
    if not path.exists():
        return None
    ttl = settings.cache_ttl_hours if ttl_hours is None else ttl_hours
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if ttl > 0 and time.time() - entry.get("stored_at", 0) > ttl * 3600:
        return None
    return entry.get("payload")


def get_stale(namespace: str, key: str) -> Any | None:
    """Return the cached payload regardless of age (used when the live source is down)."""
    return get(namespace, key, ttl_hours=0)


def put(namespace: str, key: str, payload: Any) -> None:
    try:
        settings.cache_dir.mkdir(parents=True, exist_ok=True)
        _path(namespace, key).write_text(
            json.dumps({"stored_at": time.time(), "key": key, "payload": payload}),
            encoding="utf-8",
        )
    except OSError:
        pass  # a read-only disk must never break a request
