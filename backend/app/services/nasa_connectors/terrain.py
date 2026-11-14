"""SRTM 30 m terrain: elevation, slope and local relief for a field.

Uses the keyless OpenTopoData mirror of NASA SRTM GL1 (one request for a 3x3 window).
"""
from __future__ import annotations

from app.services.nasa_connectors import base
from app.utils.geo import offset_latlon, slope_from_grid

OPENTOPO_URL = "https://api.opentopodata.org/v1/srtm30m"
WINDOW_M = 90.0  # 3 SRTM cells: smooths radar speckle on near-flat cropland


def fetch_terrain(lat: float, lon: float) -> dict:
    points = [
        offset_latlon(lat, lon, north * WINDOW_M, east * WINDOW_M)
        for north in (1, 0, -1)
        for east in (-1, 0, 1)
    ]
    locations = "|".join(f"{la:.6f},{lo:.6f}" for la, lo in points)
    payload, access = base.fetch("srtm", OPENTOPO_URL, params={"locations": locations})
    try:
        elev = [float(r["elevation"]) for r in payload["results"]]
        grid = [elev[0:3], elev[3:6], elev[6:9]]
    except (KeyError, TypeError, ValueError) as exc:
        raise base.ConnectorError(f"unexpected SRTM payload: {exc}") from exc
    stats = slope_from_grid(grid, WINDOW_M)
    return {
        "elevation_m": round(grid[1][1], 1),
        "slope_pct": round(stats["slope_pct"], 2),
        "aspect_deg": round(stats["aspect_deg"], 0),
        "relief_m": round(stats["relief_m"], 1),
        "provenance": base.provenance(
            "NASA SRTM", "SRTM GL1 30 m elevation (3x3 window, Horn slope)", access,
            resolution_m=30, cadence="static (Feb 2000)", url="https://earthdata.nasa.gov/data/instruments/srtm",
            note="Slope is a ~180 m average; micro-relief, terraces and waterways are not resolved.",
        ),
    }
