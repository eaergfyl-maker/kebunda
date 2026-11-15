"""Kebunda API entry point.

    cd backend
    uvicorn app.main:app --reload --port 8000

Interactive docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.middleware import errors, timing
from app.api.routes import load_routers
from app.config import API_PREFIX, settings
from app.services import analysis, field_store
from app.services.source_registry import SOURCES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.environment != "test":
        # run the default comparison for each benchmark farm in the background so first clicks are instant
        threading.Thread(target=analysis.warm_cache, name="warm-cache", daemon=True).start()
    yield


app = FastAPI(
    title="Kebunda API",
    version=VERSION,
    summary="Crop-rotation decision support for Malaysian farms from NASA Earth observations, global soil and crop data, and farmer priorities.",
    description=(
        "Fuses NASA POWER, GPM IMERG, SMAP, SRTM, MODIS and GRACE with Copernicus Sentinel-2, ISRIC SoilGrids, FAO GAEZ and "
        "MetMalaysia rain gauges (NOAA GHCN-Daily), then simulates "
        "and compares crop rotations for one field. Every strategy explains why it was suggested, the evidence, the expected "
        "benefits, the information gaps and the risks that need local review.\n\n" + analysis.DISCLAIMER
    ),
    lifespan=lifespan,
    openapi_tags=[
        {"name": "farms", "description": "Benchmark farms and custom fields built live from a coordinate."},
        {"name": "nasa", "description": "Live NASA POWER queries, GIBS map layers and mission notes."},
        {"name": "soil-crops", "description": "Soil properties, crop catalogue, Sentinel-2 crop cycles, GAEZ suitability and markets."},
        {"name": "rotations", "description": "Generate, score and explain rotation strategies."},
        {"name": "scenarios", "description": "What-if climate and water stress tests."},
    ],
)
app.add_middleware(GZipMiddleware, minimum_size=2000)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["Server-Timing"])
timing.install(app)
errors.install(app)
for router in load_routers():
    app.include_router(router, prefix=API_PREFIX)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "version": VERSION, "benchmark_farms": len(field_store.list_benchmarks()), "offline": settings.offline}


@app.get(f"{API_PREFIX}/meta", tags=["meta"])
def meta() -> dict:
    return {"name": "Kebunda", "version": VERSION, "disclaimer": analysis.DISCLAIMER, "sources": SOURCES,
            "challenge": "NASA Space Apps Challenge 2026 - Field Shift: Adapting Farms with NASA Data"}
