"""Keyless satellite land-product subsets from the ORNL DAAC (NASA) web service.

Covers the field-scale sensors the challenge names:
  * MODIS MOD13Q1  NDVI/EVI   250 m, 16-day   (vegetation vigor, bare-field detection)
  * MODIS MOD11A2  LST        1 km,  8-day    (thermal stress; ECOSTRESS stand-in)
  * MODIS MOD16A2GF ET        500 m, 8-day    (actual evapotranspiration)
  * VIIRS VNP13A1  NDVI       500 m, 16-day
  * SMAP SPL3SMP_E, ECOSTRESS ECO4WUE, GEDI04_B where the service holds them for a site.

The service returns at most 10 composites per request, so `fetch_series` walks the date
list in chunks. API: https://modis.ornl.gov/data/modis_webservice.html
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from app.services.nasa_connectors import base
from app.utils import cache

ORNL_URL = "https://modis.ornl.gov/rst/api/v1"
CHUNK = 10
_GATE = threading.Semaphore(3)  # the service rejects bursts, so cap concurrent requests process-wide

PRODUCTS = {
    "ndvi": {
        "product": "MOD13Q1", "band": "250m_16_days_NDVI", "scale": 0.0001,
        "valid": (-2000, 10000), "resolution_m": 250, "cadence": "16-day",
        "label": "MODIS Terra NDVI (MOD13Q1)",
    },
    "lst_day": {
        "product": "MOD11A2", "band": "LST_Day_1km", "scale": 0.02, "offset": -273.15,
        "valid": (7500, 65535), "resolution_m": 1000, "cadence": "8-day",
        "label": "MODIS Terra daytime land-surface temperature (MOD11A2)",
    },
    "et": {
        "product": "MOD16A2GF", "band": "ET_500m", "scale": 0.1,
        "valid": (0, 32700), "resolution_m": 500, "cadence": "8-day",
        "label": "MODIS evapotranspiration, gap-filled (MOD16A2GF)",
    },
    "ndvi_viirs": {
        "product": "VNP13A1", "band": "500_m_16_days_NDVI", "scale": 0.0001,
        "valid": (-10000, 10000), "resolution_m": 500, "cadence": "16-day",
        "label": "VIIRS NDVI (VNP13A1)",
    },
    "smap_sm": {
        "product": "SPL3SMP_E", "band": "soil_moisture", "scale": 1.0,
        "valid": (0.0, 1.0), "resolution_m": 9000, "cadence": "daily",
        "label": "SMAP enhanced L3 surface soil moisture (SPL3SMP_E)",
    },
}


def _get(path: str, params: dict) -> tuple[dict | str, str]:
    with _GATE:
        return base.fetch(
            "ornl", f"{ORNL_URL}/{path}", params=params,
            headers={"Accept": "application/json"}, timeout_s=60, retries=4,
        )


def available_dates(product: str, lat: float, lon: float) -> list[dict]:
    key = f"{product}:{lat:.4f},{lon:.4f}"
    if cache.get("ornl-nodata", key, ttl_hours=24 * 30):
        return []
    try:
        payload, _ = _get(f"{product}/dates", {"latitude": lat, "longitude": lon})
    except base.ConnectorError as exc:
        if "400" in str(exc) or "404" in str(exc):
            cache.put("ornl-nodata", key, True)  # remember that this product does not cover the site
            return []
        raise
    if not isinstance(payload, dict):
        return []  # the service answers with a plain string when a site has no data
    return payload.get("dates", [])


def fetch_series(kind: str, lat: float, lon: float, start: str, end: str, workers: int = 3) -> dict:
    """Return {"dates": ["YYYY-MM-DD"], "values": [float|None], "provenance": {...}}.

    `start` / `end` are ISO dates. Values are scaled to physical units; fill and
    out-of-range pixels (cloud, snow, no retrieval) become None.
    """
    spec = PRODUCTS[kind]
    dates = [
        d for d in available_dates(spec["product"], lat, lon)
        if start <= d["calendar_date"] <= end
    ]
    if not dates:
        raise base.ConnectorError(f"{spec['product']} holds no data at {lat:.3f},{lon:.3f}")
    chunks = [dates[i : i + CHUNK] for i in range(0, len(dates), CHUNK)]
    accesses: list[str] = []

    def pull(chunk: list[dict]) -> list[tuple[str, float | None]]:
        payload, access = _get(
            f"{spec['product']}/subset",
            {
                "latitude": lat, "longitude": lon, "band": spec["band"],
                "startDate": chunk[0]["modis_date"], "endDate": chunk[-1]["modis_date"],
                "kmAboveBelow": 0, "kmLeftRight": 0,
            },
        )
        accesses.append(access)
        rows = payload.get("subset", []) if isinstance(payload, dict) else []
        return [(row["calendar_date"], _scale(row["data"], spec)) for row in rows]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = [pair for part in pool.map(pull, chunks) for pair in part]
    results.sort()
    access = base.ACCESS_LIVE if base.ACCESS_LIVE in accesses else base.ACCESS_CACHE
    return {
        "dates": [d for d, _ in results],
        "values": [v for _, v in results],
        "provenance": base.provenance(
            "NASA ORNL DAAC", spec["label"], access,
            resolution_m=spec["resolution_m"], cadence=spec["cadence"],
            period=f"{start[:4]}-{end[:4]}", url="https://modis.ornl.gov/",
        ),
    }


def _scale(data: list, spec: dict) -> float | None:
    if not data:
        return None
    try:
        raw = float(data[0])
    except (TypeError, ValueError):
        return None
    lo, hi = spec["valid"]
    if raw < lo or raw > hi:
        return None
    return round(raw * spec["scale"] + spec.get("offset", 0.0), 4)
