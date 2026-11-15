"""Runtime configuration. Every core feature works with zero API keys."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    """Minimal .env reader so the service has no dependency on python-dotenv."""
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("ENVIRONMENT", "development")
    port: int = int(os.getenv("PORT", "8000"))
    cors_origins: list[str] = field(
        default_factory=lambda: [
            o.strip()
            for o in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
            ).split(",")
            if o.strip()
        ]
    )
    data_dir: Path = Path(os.getenv("FIELDSHIFT_DATA_DIR", str(REPO_ROOT / "data")))
    # Set FIELDSHIFT_OFFLINE=1 to forbid all outbound requests (tests, demos without wifi).
    offline: bool = os.getenv("FIELDSHIFT_OFFLINE", "0") == "1"
    http_timeout_s: float = float(os.getenv("FIELDSHIFT_HTTP_TIMEOUT", "45"))
    cache_ttl_hours: float = float(os.getenv("FIELDSHIFT_CACHE_TTL_HOURS", "720"))
    # Optional keys: each one only unlocks an *extra* live source.
    nasa_earthdata_token: str = os.getenv("NASA_EARTHDATA_TOKEN", "")

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"


settings = Settings()

API_PREFIX = "/api/v1"
CLIMATE_START_YEAR = 2001
CLIMATE_END_YEAR = 2024
