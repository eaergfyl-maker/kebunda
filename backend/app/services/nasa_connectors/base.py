"""Shared HTTP plumbing for every live connector (NASA and USDA).

Design rules:
  * every call is cached under data/cache/ and falls back to a stale cache entry when the
    live service is unreachable;
  * every connector returns a `provenance` dict so the UI can show exactly where a number
    came from (live service, cache, curated fallback, or model proxy);
  * `set_transport()` lets tests inject an httpx.MockTransport, so the suite runs offline.
"""
from __future__ import annotations

import datetime as dt
import logging
import time
from typing import Any

import httpx

from app.config import settings
from app.utils import cache

log = logging.getLogger("fieldshift.connectors")

_transport: httpx.BaseTransport | None = None

# access levels, ordered from most to least trustworthy
ACCESS_LIVE = "live"
ACCESS_CACHE = "cache"
ACCESS_CURATED = "curated"  # hand-assembled from published sources, shipped in data/
ACCESS_PROXY = "proxy"  # a different (modelled or coarser) product standing in
ACCESS_UNAVAILABLE = "unavailable"


class ConnectorError(RuntimeError):
    """Raised when a live source cannot be reached and no cached copy exists."""


def set_transport(transport: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = transport


def provenance(
    source: str,
    dataset: str,
    access: str,
    *,
    resolution_m: float | None = None,
    cadence: str | None = None,
    period: str | None = None,
    url: str | None = None,
    note: str | None = None,
) -> dict:
    return {
        "source": source,
        "dataset": dataset,
        "access": access,
        "resolution_m": resolution_m,
        "cadence": cadence,
        "period": period,
        "url": url,
        "note": note,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }


def fetch(
    namespace: str,
    url: str,
    *,
    params: dict | None = None,
    method: str = "GET",
    json_body: Any = None,
    headers: dict | None = None,
    as_text: bool = False,
    ttl_hours: float | None = None,
    timeout_s: float | None = None,
    retries: int = 2,
) -> tuple[Any, str]:
    """Fetch JSON (or text) with caching. Returns (payload, access) where access is live|cache."""
    key = f"{method} {url} {sorted((params or {}).items())} {json_body}"
    cached = cache.get(namespace, key, ttl_hours)
    if cached is not None:
        return cached, ACCESS_CACHE
    if settings.offline and _transport is None:
        stale = cache.get_stale(namespace, key)
        if stale is not None:
            return stale, ACCESS_CACHE
        raise ConnectorError(f"offline mode: {namespace} has no cached response")

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with httpx.Client(
                timeout=timeout_s or settings.http_timeout_s,
                transport=_transport,
                follow_redirects=True,
                headers={"User-Agent": "fieldshift-decision-support/1.0", **(headers or {})},
            ) as client:
                resp = client.request(method, url, params=params, json=json_body)
                resp.raise_for_status()
                payload = resp.text if as_text else resp.json()
            cache.put(namespace, key, payload)
            return payload, ACCESS_LIVE
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            if status is not None and 400 <= status < 500 and status != 429:
                break  # the request itself is wrong or the site has no data: retrying cannot help
            log.warning("%s attempt %d failed: %s", namespace, attempt + 1, str(exc).splitlines()[0])
            if attempt < retries and _transport is None:
                time.sleep(1.5 * (attempt + 1))  # services such as ORNL answer 503 when hit too fast
    stale = cache.get_stale(namespace, key)
    if stale is not None:
        return stale, ACCESS_CACHE
    raise ConnectorError(f"{namespace} unreachable: {str(last_error).splitlines()[0]}")
