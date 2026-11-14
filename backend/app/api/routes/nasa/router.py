"""Live NASA queries and map-layer metadata."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.schemas.responses import ErrorResponse
from app.services.fusion_engine import climate
from app.services.nasa_connectors import gibs, missions, power, terrain
from app.services.source_registry import SOURCES
from app.utils.geo import MONTH_NAMES

router = APIRouter(prefix="/nasa", tags=["nasa"])
UPSTREAM = {503: {"model": ErrorResponse}}

Lat = Query(..., ge=-60, le=72, description="Latitude in decimal degrees")
Lon = Query(..., ge=-180, le=180, description="Longitude in decimal degrees")


@router.get("/power", responses=UPSTREAM, summary="Live NASA POWER climate summary for any coordinate")
def power_point(lat: float = Lat, lon: float = Lon) -> dict:
    """24 years of daily NASA POWER (MERRA-2 + GPM IMERG) summarised to monthly normals, frost
    dates, extremes and trends. Keyless. First call for a coordinate takes a few seconds."""
    daily = power.fetch_daily(lat, lon)
    s = climate.summarise_daily(daily, lat)
    mo = s["monthly"]
    warmest = max(range(12), key=lambda m: mo["tmax"][m])
    wettest = max(range(12), key=lambda m: mo["precip"][m])
    return {
        "lat": lat, "lon": lon, "grid_elevation_m": daily.get("grid_elevation_m"),
        "annual_precip_mm": s["annual_precip_mm"], "annual_et0_mm": s["annual_et0_mm"],
        "mean_annual_temp_c": s["mean_annual_temp_c"], "aridity_index": s["aridity_index"],
        "frost": s["frost"], "monthly": mo, "annual": s["annual"], "trends": s["trends"], "years": s["years"],
        "headline": (f"{s['annual_precip_mm']:.0f} mm of precipitation a year, wettest in {MONTH_NAMES[wettest]}; "
                     f"average highs peak at {mo['tmax'][warmest]:.0f} C in {MONTH_NAMES[warmest]}; "
                     f"about {s['frost']['frost_free_days_median']:.0f} frost-free days."),
        "provenance": daily["provenance"],
    }


@router.get("/terrain", responses=UPSTREAM, summary="SRTM elevation and slope at a coordinate")
def terrain_point(lat: float = Lat, lon: float = Lon) -> dict:
    return terrain.fetch_terrain(lat, lon)


@router.get("/gibs/layers", summary="NASA GIBS / Worldview map layers")
def gibs_layers(check: bool = Query(False, description="Verify each layer against the live GIBS capabilities document")) -> dict:
    """WMTS layer catalogue with ready-to-use XYZ tile templates ({z}/{y}/{x}, {time} = YYYY-MM-DD)."""
    out = {"layers": gibs.catalogue(), "tile_matrix_note": "EPSG:3857. Do not request tiles beyond each layer's max_zoom.",
           "legend_note": "Legend colour stops are approximate guides, not the official GIBS colour maps."}
    if check:
        out["live_check"] = gibs.check_live()
    return out


@router.get("/missions", summary="What each NASA mission contributes and how it is accessed")
def mission_notes() -> dict:
    return {"missions": missions.MISSION_NOTES, "grace_regions": missions.GRACE_REGIONS}


@router.get("/sources", summary="Every dataset on the challenge resource list and how it is used")
def sources() -> dict:
    counts: dict[str, int] = {}
    for s in SOURCES:
        counts[s["status"]] = counts.get(s["status"], 0) + 1
    return {"sources": SOURCES, "status_counts": counts}
