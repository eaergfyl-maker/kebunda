"""Request logging plus a Server-Timing header so the UI can show how long a model run took."""
from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request

log = logging.getLogger("fieldshift.api")


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def timing(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000
        response.headers["Server-Timing"] = f"app;dur={ms:.0f}"
        if request.url.path.startswith("/api/"):
            log.info("%s %s -> %s in %.0f ms", request.method, request.url.path, response.status_code, ms)
        return response
