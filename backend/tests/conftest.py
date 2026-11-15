"""Shared fixtures. The suite never touches the network: benchmark farms come from data/,
and connector tests inject an httpx.MockTransport."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["ENVIRONMENT"] = "test"
os.environ["KEBUNDA_OFFLINE"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.config import settings  # noqa: E402
from app.services import analysis, field_store  # noqa: E402
from app.services.nasa_connectors import base  # noqa: E402

FARM_IDS = field_store.benchmark_ids()


@pytest.fixture(scope="session")
def farm_ids() -> list[str]:
    assert len(FARM_IDS) >= 4, "benchmark farms are missing from data/benchmark-farms"
    return FARM_IDS


@pytest.fixture(scope="session")
def kedah():
    """Irrigated double-crop paddy in the MADA scheme: (bundle, neutral context)."""
    b = analysis.bundle("kedah-mada")
    return b, analysis.context(b)


@pytest.fixture(scope="session")
def kelantan():
    """Rainfed kenaf on BRIS coastal sand: (bundle, neutral context)."""
    b = analysis.bundle("kelantan-bris")
    return b, analysis.context(b)


@pytest.fixture(scope="session")
def cameron():
    """Steep highland vegetable terrace: (bundle, neutral context)."""
    b = analysis.bundle("cameron-highlands")
    return b, analysis.context(b)


@pytest.fixture()
def mock_http(tmp_path, monkeypatch):
    """Route connector HTTP through a handler and give the cache a clean folder.

    Usage: mock_http(lambda request: httpx.Response(200, json={...}))
    """
    monkeypatch.setattr(type(settings), "cache_dir", property(lambda self: tmp_path))
    calls: list[httpx.Request] = []

    def install(handler):
        def wrapped(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return handler(request)

        base.set_transport(httpx.MockTransport(wrapped))
        return calls

    yield install
    base.set_transport(None)
