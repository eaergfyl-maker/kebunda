"""Assemble every observation layer for one coordinate.

Used two ways:
  * `scripts/build_benchmark_data.py` runs it once per benchmark farm and stores the result
    in data/benchmark-farms/observations/, so the demo is instant and works offline;
  * the custom-field endpoint runs it live for any coordinate a farmer clicks.

Sources: NASA POWER (MERRA-2 + GPM IMERG), SMAP-class soil wetness, SRTM, MODIS and GRACE
from NASA; ISRIC SoilGrids, FAO GAEZ, Copernicus Sentinel-2 and NOAA GHCN-Daily gauges for
the soil, suitability, field-scale greenness and ground truth that U.S. agencies cannot supply
for Malaysia.

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
from app.services.global_connectors import gaez, ghcn, sentinel2, soilgrids
from app.services.nasa_connectors import base, land_products, missions, power, terrain

log = logging.getLogger("kebunda.observe")

LAND_START, LAND_END = "2019-01-01", "2023-12-31"
S2_START, S2_END = "2020-01-01", "2024-12-31"
THERMAL_START = "2021-01-01"
OPTIONAL_LAYER_BUDGET_S = 30.0
SOIL_BUDGET_S = 50.0


def _try(label: str, issues: list[dict], fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except base.ConnectorError as exc:
        issues.append({"layer": label, "problem": str(exc)})
        log.warning("layer %s unavailable: %s", label, exc)
        return None


def collect(lat: float, lon: float, *, depth: str = "full", irrigated: bool = False, with_modis: bool = True) -> dict:
    """depth="full" pulls every layer (benchmarks); depth="fast" pulls two recent years of
    Sentinel-2, skips the slow MODIS thermal stacks and the GAEZ 2050s projections so a clicked
    field answers in seconds; depth="lite" also skips Sentinel-2. with_modis=False leaves out
    the MODIS stacks (ORNL subsetting service) when that service is down."""
    from app.services.rotation_engine.context import crops_by_id

    issues: list[dict] = []
    # An interactive (custom field) request must answer in seconds even when a secondary
    # service is slow, so optional layers get a time budget. A layer that misses it is
    # reported as an issue; its thread keeps running and fills the cache for next time.
    budget = None if depth == "full" else OPTIONAL_LAYER_BUDGET_S
    full = depth == "full"
    pool = ThreadPoolExecutor(max_workers=7)
    try:
        f_power = pool.submit(_try, "nasa_power", issues, power.fetch_daily, lat, lon)
        f_soil = pool.submit(_try, "soilgrids", issues, soilgrids.fetch_soil_profile, lat, lon)
        f_terrain = pool.submit(_try, "srtm", issues, terrain.fetch_terrain, lat, lon)
        f_ndvi = None
        if depth != "lite":
            f_ndvi = pool.submit(_try, "sentinel2_ndvi", issues, sentinel2.fetch_ndvi, lat, lon,
                                 S2_START if full else "2023-01-01", S2_END, max_cloud=80.0 if full else 60.0)
        f_ground = pool.submit(_try, "ghcn_gauge", issues, ghcn.fetch_gauge, lat, lon,
                               CLIMATE_START_YEAR if full else 2014, CLIMATE_END_YEAR)
        f_gaez = pool.submit(gaez.crop_suitability, lat, lon, crops_by_id(), irrigated=irrigated, with_future=full)
        f_lst = f_et = f_modis = None
        if full and with_modis:
            f_modis = pool.submit(_try, "modis_ndvi", issues, land_products.fetch_series, "ndvi", lat, lon, LAND_START, LAND_END)
            f_lst = pool.submit(_try, "modis_lst", issues, land_products.fetch_series, "lst_day", lat, lon, THERMAL_START, LAND_END)
            f_et = pool.submit(_try, "modis_et", issues, land_products.fetch_series, "et", lat, lon, THERMAL_START, LAND_END)
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
        soil = within_budget("soilgrids", f_soil, SOIL_BUDGET_S)
        terr = within_budget("srtm", f_terrain)
        ground = within_budget("ghcn_gauge", f_ground)
        ndvi = within_budget("sentinel2_ndvi", f_ndvi)
        suit = within_budget("gaez", f_gaez)
        modis = within_budget("modis_ndvi", f_modis)
        lst, et = within_budget("modis_lst", f_lst), within_budget("modis_et", f_et)
    finally:
        pool.shutdown(wait=False)

    if p is None:
        raise base.ConnectorError("NASA POWER is unreachable and no cached record exists for this coordinate")

    obs = {
        "lat": lat, "lon": lon, "depth": depth,
        "climate": {**climate.summarise_daily(p, lat), "provenance": p["provenance"],
                    "grid_elevation_m": p.get("grid_elevation_m")},
        "precip_comparison": climate.compare_precip_sources(p, ground),
        "soil_moisture": _soil_moisture_block(lat, lon, p, try_smap=full),
        # Sentinel-2 (10 m) is the field-scale greenness record; MODIS (250 m) is kept as the
        # longer, coarser cross-check when ORNL DAAC answers.
        "ndvi": climate.monthly_climatology(ndvi) if ndvi else (climate.monthly_climatology(modis) if modis else None),
        "ndvi_modis": climate.monthly_climatology(modis) if (modis and ndvi) else None,
        "ndvi_series": {"dates": ndvi["dates"], "values": ndvi["values"]} if ndvi else None,
        "crop_cycles": sentinel2.crop_cycles(ndvi),
        "lst": climate.monthly_climatology(lst) if lst else None,
        "et": climate.monthly_climatology(et, how="rate8") if et else None,
        "thermal_provenance": missions.ecostress_thermal(lst, et)["provenance"],
        "grace": missions.grace_water_storage(lat, lon),
        "gaez": suit,
        "terrain": terr,
        "soil": soil,
        "issues": issues,
    }
    return obs


def _soil_moisture_block(lat: float, lon: float, p: dict, try_smap: bool = True) -> dict:
    sm = missions.smap_soil_moisture(lat, lon, p, "2022-01-01", "2023-12-31", try_live=try_smap)
    block = {"kind": sm["kind"], "provenance": sm["provenance"]}
    if sm["kind"] == "smap_l3":
        block["smap_monthly"] = climate.monthly_climatology(sm)
    return block
