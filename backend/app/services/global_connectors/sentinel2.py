"""Copernicus Sentinel-2 L2A 10 m NDVI at a point, via the Microsoft Planetary Computer.

Both steps are keyless:
  1. STAC search for every Sentinel-2 L2A scene over the point (cloud filter on the tile);
  2. the Planetary Computer data API reads the red (B04), near-infrared (B08) and
     scene-classification (SCL) pixel under the point for each scene.

Pixels the scene classification marks as cloud, shadow, cirrus or no-data are dropped, so a
cloudy tropical month simply has fewer observations. Scenes processed with baseline 04.00
or later carry a +1000 reflectance offset, which is removed before NDVI is computed.

`crop_cycles()` turns the series into the number of green-up / harvest cycles per year:
the satellite answer to "how many crops a year does this field carry?", which replaces
the USDA Cropland Data Layer, which only covers the United States.
"""
from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor

from app.services.nasa_connectors import base

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
POINT_URL = "https://planetarycomputer.microsoft.com/api/data/v1/item/point/{lon},{lat}"
COLLECTION = "sentinel-2-l2a"
VALID_SCL = {4, 5, 6}  # vegetation, bare soil, water (a flooded paddy is real information)
BOA_OFFSET = 1000.0


def _search(lat: float, lon: float, start: str, end: str, max_cloud: float) -> list[dict]:
    body = {
        "collections": [COLLECTION], "intersects": {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]},
        "datetime": f"{start}/{end}", "limit": 250, "query": {"eo:cloud_cover": {"lt": max_cloud}},
        "sortby": [{"field": "datetime", "direction": "asc"}],
    }
    items: list[dict] = []
    for _page in range(20):
        payload, _ = base.fetch("s2-stac", STAC_URL, method="POST", json_body=body, timeout_s=90, ttl_hours=24 * 30)
        for f in payload.get("features", []):
            p = f.get("properties", {})
            items.append({"id": f["id"], "datetime": p.get("datetime", "")[:10], "cloud": p.get("eo:cloud_cover"),
                          "baseline": p.get("s2:processing_baseline") or "00.00", "tile": p.get("s2:mgrs_tile")})
        nxt = next((link for link in payload.get("links", []) if link.get("rel") == "next"), None)
        if not nxt or not nxt.get("body"):
            break
        body = nxt["body"]
    # a point on a tile overlap is imaged twice per pass: keep one scene per date (the clearer one)
    by_date: dict[str, dict] = {}
    for it in items:
        cur = by_date.get(it["datetime"])
        if cur is None or (it["cloud"] or 100) < (cur["cloud"] or 100):
            by_date[it["datetime"]] = it
    return [by_date[d] for d in sorted(by_date)]


def _pixel(item: dict, lat: float, lon: float) -> float | None:
    try:
        payload, _ = base.fetch(
            "s2-point", POINT_URL.format(lon=round(lon, 5), lat=round(lat, 5)),
            params=[("collection", COLLECTION), ("item", item["id"]), ("assets", "B04"), ("assets", "B08"), ("assets", "SCL")],
            timeout_s=60, retries=1,
        )
    except base.ConnectorError:
        return None
    vals = payload.get("values") or []
    if len(vals) < 3 or any(v is None for v in vals):
        return None
    red, nir, scl = float(vals[0]), float(vals[1]), int(vals[2])
    if scl not in VALID_SCL or red <= 0 or nir <= 0:
        return None
    if item["baseline"] >= "04.00":
        red, nir = red - BOA_OFFSET, nir - BOA_OFFSET
    if red <= 0 or nir <= 0 or red + nir <= 0:
        return None
    return round((nir - red) / (nir + red), 4)


def fetch_ndvi(lat: float, lon: float, start: str, end: str, *, max_cloud: float = 80.0, workers: int = 6) -> dict:
    """Return {"dates": [...], "values": [...], "provenance": {...}} like the MODIS land-product series."""
    items = _search(lat, lon, start, end, max_cloud)
    if not items:
        raise base.ConnectorError("no Sentinel-2 scenes over this point in the period")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        values = list(pool.map(lambda it: _pixel(it, lat, lon), items))
    pairs = [(it["datetime"], v) for it, v in zip(items, values) if v is not None]
    if len(pairs) < 6:
        raise base.ConnectorError(f"only {len(pairs)} cloud-free Sentinel-2 looks at this point")
    return {
        "dates": [d for d, _ in pairs],
        "values": [v for _, v in pairs],
        "scenes_searched": len(items),
        "provenance": base.provenance(
            "ESA Copernicus Sentinel-2 (Microsoft Planetary Computer)", "Sentinel-2 L2A NDVI (B08/B04), SCL cloud mask",
            base.ACCESS_LIVE, resolution_m=10, cadence="5-day revisit (cloud permitting)", period=f"{start[:4]}-{end[:4]}",
            url="https://planetarycomputer.microsoft.com/dataset/sentinel-2-l2a",
            note=(f"{len(pairs)} clear looks out of {len(items)} scenes. Monsoon cloud leaves gaps of several weeks; "
                  "a single 10 m pixel can sit on a bund, drain or path, so check the point on imagery."),
        ),
    }


def _smooth(dates: list[str], values: list[float], step_days: int = 8, window_days: int = 24) -> list[tuple[dt.date, float]]:
    """Regular series by a moving median, which shrugs off the odd hazy look."""
    obs = [(dt.date.fromisoformat(d), v) for d, v in zip(dates, values)]
    if not obs:
        return []
    out = []
    day = obs[0][0]
    while day <= obs[-1][0]:
        near = sorted(v for d, v in obs if abs((d - day).days) <= window_days)
        if len(near) >= 2:
            out.append((day, near[len(near) // 2]))
        day += dt.timedelta(days=step_days)
    return out


def crop_cycles(series: dict | None, min_amplitude: float = 0.15) -> dict | None:
    """Count crop cycles per year: a green peak flanked by low points at least `min_amplitude` lower."""
    if not series or len(series.get("values", [])) < 12:
        return None
    sm = _smooth(series["dates"], series["values"])
    if len(sm) < 10:
        return None
    vals = [v for _, v in sm]
    peaks = []
    for i in range(1, len(vals) - 1):
        if vals[i] < vals[i - 1] or vals[i] < vals[i + 1] or vals[i] < 0.35:
            continue
        left = min(vals[max(0, i - 12):i] or [vals[i]])
        right = min(vals[i + 1:i + 13] or [vals[i]])
        if vals[i] - left >= min_amplitude and vals[i] - right >= min_amplitude:
            if not peaks or (sm[i][0] - peaks[-1][0]).days > 60:
                peaks.append((sm[i][0], vals[i]))
            elif vals[i] > peaks[-1][1]:
                peaks[-1] = (sm[i][0], vals[i])
    years = sorted({d.year for d, _ in sm})
    span_days = max(1, (sm[-1][0] - sm[0][0]).days)
    per_year = [{"year": y, "cycles": sum(1 for d, _ in peaks if d.year == y),
                 "peak_dates": [d.isoformat() for d, _ in peaks if d.year == y]} for y in years]
    peak_months = [0] * 12
    for d, _ in peaks:
        peak_months[d.month - 1] += 1
    return {
        "years": per_year,
        "cycles_per_year": round(len(peaks) / (span_days / 365.25), 2),
        "peak_month_counts": peak_months,
        "evergreen": min(vals) >= 0.55,
        "provenance": {**series["provenance"], "dataset": "Crop cycles counted from Sentinel-2 NDVI peaks"},
    }
