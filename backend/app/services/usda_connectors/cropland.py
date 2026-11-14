"""Crop history, yields, field-scale ET and prices: CDL / CropScape, NASS QuickStats, OpenET,
USDA AMS Market News.

Every function tries the live service when it can (CropScape is keyless; NASS and OpenET
need a free key in .env) and otherwise returns the curated fallback shipped in data/,
always labelled so the UI can say which one the farmer is looking at.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from app.config import settings
from app.services.nasa_connectors import base
from app.utils.geo import albers_conus

CROPSCAPE_URL = "https://nassgeodata.gmu.edu/axis2/services/CDLService/GetCDLValue"
NASS_URL = "https://quickstats.nass.usda.gov/api/api_GET/"
OPENET_URL = "https://openet-api.org/raster/timeseries/point"

# CDL class code -> FieldShift crop id (None = not a rotation crop we model)
CDL_TO_CROP = {
    1: "corn", 2: "cotton", 3: "rice", 4: "sorghum", 5: "soybean", 6: "sunflower", 21: "barley",
    22: "winter_wheat", 23: "spring_wheat", 24: "winter_wheat", 26: "winter_wheat", 27: "cereal_rye",
    28: "oats", 29: "millet", 31: "canola", 36: "alfalfa", 37: "alfalfa", 42: "dry_bean", 51: "chickpea",
    52: "lentil", 53: "dry_pea", 54: "tomato", 61: "fallow", 205: "triticale", 225: "winter_wheat",
    226: "oats", 236: "winter_wheat", 237: "barley", 238: "winter_wheat",
}
CDL_DOUBLE_CROP = {26: ["winter_wheat", "soybean"], 225: ["winter_wheat", "corn"], 236: ["winter_wheat", "sorghum"],
                   238: ["winter_wheat", "cotton"]}


def cdl_history(lat: float, lon: float, years: list[int]) -> dict:
    """Crop type at a point for each year from the 30 m Cropland Data Layer."""
    x, y = albers_conus(lat, lon)
    out, access_seen = [], set()

    def one(year: int):
        try:
            xml, access = base.fetch(
                "cdl", CROPSCAPE_URL, params={"year": year, "x": round(x), "y": round(y)},
                as_text=True, timeout_s=20, retries=0,
            )
        except base.ConnectorError:
            return None
        match = re.search(r'value:\s*"?(\d+)"?,\s*category:\s*"([^"]+)"', xml)
        return (year, int(match.group(1)), match.group(2), access) if match else None

    with ThreadPoolExecutor(max_workers=6) as pool:  # one request per year, in parallel
        for hit in pool.map(one, years):
            if hit is None:
                continue
            year, code, name, access = hit
            access_seen.add(access)
            out.append({"year": year, "cdl_code": code, "cdl_class": name,
                        "crop_id": CDL_TO_CROP.get(code), "double_crop": CDL_DOUBLE_CROP.get(code)})
    ok = bool(out)
    return {
        "years": out,
        "provenance": base.provenance(
            "USDA NASS", "Cropland Data Layer (CropScape point query)",
            (base.ACCESS_LIVE if base.ACCESS_LIVE in access_seen else base.ACCESS_CACHE) if ok else base.ACCESS_UNAVAILABLE,
            resolution_m=30, cadence="annual", url="https://nassgeodata.gmu.edu/CropScape/",
            note=None if ok else "CropScape did not answer. The baseline rotation falls back to the regional norm; confirm it.",
        ),
    }


def nass_county_yield(commodity: str, state_alpha: str, county: str, year_from: int = 2014) -> dict:
    """County survey yields from NASS QuickStats (needs USDA_NASS_API_KEY)."""
    prov = dict(source="USDA NASS", dataset="QuickStats county survey yields", resolution_m=None,
                cadence="annual", url="https://quickstats.nass.usda.gov/")
    if not settings.usda_nass_api_key:
        return {"values": [], "provenance": base.provenance(
            prov["source"], prov["dataset"], base.ACCESS_UNAVAILABLE, cadence="annual", url=prov["url"],
            note="Set USDA_NASS_API_KEY in .env for live county yields. Curated reference yields are used instead.")}
    params = {
        "key": settings.usda_nass_api_key, "commodity_desc": commodity.upper(), "statisticcat_desc": "YIELD",
        "agg_level_desc": "COUNTY", "state_alpha": state_alpha, "county_name": county.upper(),
        "year__GE": year_from, "source_desc": "SURVEY", "format": "JSON",
    }
    try:
        payload, access = base.fetch("nass", NASS_URL, params=params)
    except base.ConnectorError as exc:
        return {"values": [], "provenance": base.provenance(prov["source"], prov["dataset"], base.ACCESS_UNAVAILABLE, note=str(exc))}
    values = []
    for row in payload.get("data", []):
        try:
            values.append({"year": int(row["year"]), "value": float(row["Value"].replace(",", "")),
                           "unit": row.get("unit_desc"), "practice": row.get("prodn_practice_desc")})
        except (KeyError, ValueError):
            continue
    return {"values": sorted(values, key=lambda v: v["year"]),
            "provenance": base.provenance(prov["source"], prov["dataset"], access, cadence="annual", url=prov["url"])}


def openet_monthly(lat: float, lon: float, start: str, end: str) -> dict:
    """Field-scale (30 m, Landsat-based) ensemble ET from OpenET (needs OPENET_API_KEY)."""
    url = "https://openetdata.org/"
    if not settings.openet_api_key:
        return {"values": [], "provenance": base.provenance(
            "OpenET", "Ensemble monthly ET (30 m)", base.ACCESS_UNAVAILABLE, resolution_m=30, cadence="monthly", url=url,
            note="Set OPENET_API_KEY in .env for 30 m ET in the western U.S. MODIS MOD16 (500 m) is used instead.")}
    body = {"date_range": [start, end], "interval": "monthly", "geometry": [lon, lat], "model": "Ensemble",
            "variable": "ET", "reference_et": "gridMET", "units": "mm", "file_format": "JSON"}
    try:
        payload, access = base.fetch("openet", OPENET_URL, method="POST", json_body=body,
                                     headers={"Authorization": settings.openet_api_key})
    except base.ConnectorError as exc:
        return {"values": [], "provenance": base.provenance("OpenET", "Ensemble monthly ET (30 m)", base.ACCESS_UNAVAILABLE, note=str(exc), url=url)}
    values = [{"date": row.get("time"), "et_mm": row.get("et")} for row in payload if isinstance(row, dict)]
    return {"values": values, "provenance": base.provenance("OpenET", "Ensemble monthly ET (30 m)", access, resolution_m=30, cadence="monthly", url=url)}


def market_snapshot(crops: list[dict], local_market: dict | None = None) -> dict:
    """Price level, volatility and local-buyer access per crop.

    Prices are multi-year averages curated from USDA AMS Market News / NASS marketing-year
    reports and stored in the crop catalogue. The live MARS API needs a registered key, so it
    is an optional extension; the curated table keeps the tool keyless.
    """
    local_market = local_market or {}
    rows = []
    for crop in crops:
        econ = crop.get("economics")
        if not econ:
            continue
        local = local_market.get(crop["id"], {})
        rows.append({
            "crop_id": crop["id"], "name": crop["name"],
            "price": econ["price"], "price_unit": f"$/{econ['yield_unit']}",
            "price_volatility_cv": econ["price_cv"],
            "local_access": local.get("access", crop.get("market_default", 0.5)),
            "local_note": local.get("note", "No local buyer information on file. Call elevators or processors before planting."),
            "verified_locally": bool(local),
        })
    return {
        "rows": rows,
        "provenance": base.provenance(
            "USDA AMS Market News / NASS", "Multi-year average prices and volatility (curated)", base.ACCESS_CURATED,
            cadence="2019-2024 average", url="https://ams.usda.gov/market-news",
            note="Averages hide basis, contracts and delivery distance. Use them to rank options, not to budget."),
    }
