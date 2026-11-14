"""Assemble every observation layer for one coordinate.

Used two ways:
  * `scripts/build_benchmark_data.py` runs it once per benchmark farm and stores the result
    in data/benchmark-farms/observations/, so the demo is instant and works offline;
  * the custom-field endpoint runs it live for any coordinate a farmer clicks.

Each layer is optional: a failed source is recorded in `issues` and the engines carry on
with lower confidence instead of failing the request.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from app.config import CLIMATE_END_YEAR, CLIMATE_START_YEAR
from app.services.fusion_engine import climate
from app.services.nasa_connectors import base, land_products, missions, power, terrain
from app.services.usda_connectors import cropland, ground_truth, ssurgo

log = logging.getLogger("fieldshift.observe")

LAND_START, LAND_END = "2019-01-01", "2023-12-31"
THERMAL_START = "2021-01-01"
OPTIONAL_LAYER_BUDGET_S = 25.0
SOIL_BUDGET_S = 50.0


def _try(label: str, issues: list[dict], fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except base.ConnectorError as exc:
        issues.append({"layer": label, "problem": str(exc)})
        log.warning("layer %s unavailable: %s", label, exc)
        return None


def collect(lat: float, lon: float, *, depth: str = "full") -> dict:
    """depth="full" pulls every layer (benchmarks); depth="fast" skips the slow 8-day thermal
    stacks so a clicked field answers in seconds; depth="lite" also skips MODIS NDVI, for when
    the ORNL subset service is down."""
    issues: list[dict] = []
    # An interactive (custom field) request must answer in seconds even when a secondary
    # service is slow, so optional layers get a time budget. A layer that misses it is
    # reported as an issue; its thread keeps running and fills the cache for next time.
    budget = None if depth == "full" else OPTIONAL_LAYER_BUDGET_S
    pool = ThreadPoolExecutor(max_workers=6)
    try:
        f_power = pool.submit(_try, "nasa_power", issues, power.fetch_daily, lat, lon)
        f_soil = pool.submit(_try, "ssurgo", issues, ssurgo.fetch_soil_profile, lat, lon)
        f_terrain = pool.submit(_try, "srtm", issues, terrain.fetch_terrain, lat, lon)
        f_ndvi = None
        if depth != "lite":
            f_ndvi = pool.submit(_try, "modis_ndvi", issues, land_products.fetch_series, "ndvi", lat, lon,
                                 LAND_START if depth == "full" else "2021-01-01", LAND_END)
        f_daymet = pool.submit(_try, "daymet", issues, ground_truth.fetch_daymet, lat, lon,
                               CLIMATE_START_YEAR if depth == "full" else 2014, CLIMATE_END_YEAR - 1)
        f_lst = f_et = f_cdl = None
        if depth == "full":
            f_lst = pool.submit(_try, "modis_lst", issues, land_products.fetch_series, "lst_day", lat, lon, THERMAL_START, LAND_END)
            f_et = pool.submit(_try, "modis_et", issues, land_products.fetch_series, "et", lat, lon, THERMAL_START, LAND_END)
        f_cdl = pool.submit(cropland.cdl_history, lat, lon, list(range(2018, 2024)))
        started = time.monotonic()

        def within_budget(label: str, future, limit: float | None = budget):
            if future is None:
                return None
            if budget is None:
                limit = None
            left = None if limit is None else max(0.5, limit - (time.monotonic() - started))
            try:
                return future.result(timeout=left)
            except FutureTimeout:
                issues.append({"layer": label, "problem": f"did not answer within {limit:.0f} s; left out of this run"})
                return None

        p = f_power.result()
        # soil drives most results, so it gets the longest wait
        soil = within_budget("ssurgo", f_soil, SOIL_BUDGET_S)
        terr = within_budget("srtm", f_terrain)
        daymet = within_budget("daymet", f_daymet)
        ndvi = within_budget("modis_ndvi", f_ndvi)
        lst, et = within_budget("modis_lst", f_lst), within_budget("modis_et", f_et)
        cdl = within_budget("cdl", f_cdl)
    finally:
        pool.shutdown(wait=False)

    if p is None:
        raise base.ConnectorError("NASA POWER is unreachable and no cached record exists for this coordinate")

    obs = {
        "lat": lat, "lon": lon, "depth": depth,
        "climate": {**climate.summarise_daily(p, lat), "provenance": p["provenance"],
                    "grid_elevation_m": p.get("grid_elevation_m")},
        "precip_comparison": climate.compare_precip_sources(p, daymet),
        "soil_moisture": _soil_moisture_block(lat, lon, p, try_smap=depth == "full"),
        "ndvi": climate.monthly_climatology(ndvi) if ndvi else None,
        "lst": climate.monthly_climatology(lst) if lst else None,
        "et": climate.monthly_climatology(et, how="rate8") if et else None,
        "thermal_provenance": missions.ecostress_thermal(lst, et)["provenance"],
        "grace": missions.grace_water_storage(lat, lon),
        "terrain": terr,
        "soil": soil,
        "cdl": cdl,
        "issues": issues,
    }
    return obs


def _soil_moisture_block(lat: float, lon: float, p: dict, try_smap: bool = True) -> dict:
    sm = missions.smap_soil_moisture(lat, lon, p, "2022-01-01", "2023-12-31", try_live=try_smap)
    block = {"kind": sm["kind"], "provenance": sm["provenance"]}
    if sm["kind"] == "smap_l3":
        block["smap_monthly"] = climate.monthly_climatology(sm)
    return block
