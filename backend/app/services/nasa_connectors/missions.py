"""Mission adapters: SMAP, ECOSTRESS, GPM IMERG and GRACE-FO.

Each adapter answers one farmer-facing question and is honest about how it got the answer.
Where the true product needs an Earthdata login (SMAP L4, ECOSTRESS L2/L3, GRACE mascons),
the adapter first tries a keyless route and otherwise returns a clearly-labelled *proxy*
built from a physically related NASA product. The proxy relationship and its extra
uncertainty are carried in `provenance` and surface in the UI as "information gaps".
"""
from __future__ import annotations

from app.services.nasa_connectors import base, land_products
from app.utils.geo import haversine_km

# --------------------------------------------------------------------------- SMAP


def smap_soil_moisture(lat: float, lon: float, power_daily: dict | None, start: str, end: str,
                       try_live: bool = True) -> dict:
    """Surface/root-zone soil moisture. Tries SMAP L3 (9 km); falls back to MERRA-2 wetness.

    try_live=False skips the SMAP subset lookup (interactive requests: it is slow and the
    keyless service covers few sites), going straight to the labelled proxy."""
    if try_live:
        try:
            series = land_products.fetch_series("smap_sm", lat, lon, start, end)
            return {"kind": "smap_l3", **series}
        except base.ConnectorError:
            pass
    if not power_daily:
        return {"kind": "none", "dates": [], "values": [], "provenance": base.provenance(
            "NASA SMAP", "SPL3SMP_E / SPL4SMGP", base.ACCESS_UNAVAILABLE,
            note="No keyless SMAP subset for this site and no POWER series to build a proxy.")}
    return {
        "kind": "merra2_proxy",
        "dates": power_daily["dates"],
        "values": power_daily["series"]["wet_root"],
        "surface": power_daily["series"]["wet_top"],
        "provenance": base.provenance(
            "NASA POWER (MERRA-2 land model)", "Root-zone soil wetness GWETROOT, standing in for SMAP L4",
            base.ACCESS_PROXY, resolution_m=55_000, cadence="daily",
            url="https://earthdata.nasa.gov/data/platforms/space-based-platforms/smap",
            note=("SMAP L4 root-zone moisture (9 km) needs an Earthdata login. MERRA-2 wetness is "
                  "the same kind of model-assimilated estimate at coarser resolution, so seasonal "
                  "anomalies agree well but field-to-field differences are invisible."),
        ),
    }


# ---------------------------------------------------------------------- ECOSTRESS


def ecostress_thermal(lst_series: dict | None, et_series: dict | None) -> dict:
    """Field-scale thermal stress. ECOSTRESS (70 m) needs AppEEARS auth, so MODIS LST (1 km)
    and MOD16 ET (500 m) stand in. Same physics, coarser pixels, fixed overpass time."""
    ok = bool(lst_series and lst_series.get("values"))
    return {
        "kind": "modis_proxy" if ok else "none",
        "lst": lst_series,
        "et": et_series,
        "provenance": base.provenance(
            "NASA MODIS (ECOSTRESS stand-in)", "MOD11A2 land-surface temperature + MOD16A2GF ET",
            base.ACCESS_PROXY if ok else base.ACCESS_UNAVAILABLE,
            resolution_m=1000, cadence="8-day",
            url="https://ecostress.jpl.nasa.gov/data",
            note=("ECOSTRESS resolves 70 m hotspots inside a field and samples different times of "
                  "day. MODIS sees one ~10:30 am value per 1 km pixel, so within-field hotspots "
                  "(sandy knolls, pivot corners) are averaged out."),
        ),
    }


# ------------------------------------------------------------------------ GRACE-FO

# Regional total-water-storage trends (cm of water per year), rounded from published GRACE /
# GRACE-FO mascon analyses (Rodell et al. 2018, Nature 557; Scanlon et al. 2012, PNAS 109;
# USGS and state survey well networks). GRACE resolves ~300 km, so one number covers a region.
GRACE_REGIONS = [
    {"id": "high-plains-central", "name": "Central High Plains (Ogallala) aquifer", "lat": 37.8, "lon": -100.9, "radius_km": 330,
     "tws_trend_cm_yr": -1.6, "uncertainty_cm_yr": 0.6, "driver": "irrigation pumping exceeds recharge"},
    {"id": "central-valley", "name": "California Central Valley aquifer system", "lat": 36.6, "lon": -120.0, "radius_km": 300,
     "tws_trend_cm_yr": -2.1, "uncertainty_cm_yr": 0.8, "driver": "groundwater pumping during surface-water shortfalls"},
    {"id": "mississippi-embayment", "name": "Mississippi River Valley alluvial aquifer", "lat": 33.6, "lon": -90.8, "radius_km": 260,
     "tws_trend_cm_yr": -0.4, "uncertainty_cm_yr": 0.7, "driver": "irrigation drawdown partly masked by wet-year recharge"},
    {"id": "upper-midwest", "name": "Upper Midwest / Corn Belt", "lat": 42.2, "lon": -93.6, "radius_km": 380,
     "tws_trend_cm_yr": 0.6, "uncertainty_cm_yr": 0.6, "driver": "wetter decades; storage is not the limiting factor"},
    {"id": "columbia-plateau", "name": "Columbia Plateau basalt aquifers", "lat": 46.8, "lon": -118.0, "radius_km": 280,
     "tws_trend_cm_yr": -0.3, "uncertainty_cm_yr": 0.5, "driver": "localised deep-basalt declines; dryland farming does not pump"},
]


def grace_water_storage(lat: float, lon: float) -> dict:
    best = None
    for region in GRACE_REGIONS:
        d = haversine_km(lat, lon, region["lat"], region["lon"])
        if d <= region["radius_km"] and (best is None or d < best[0]):
            best = (d, region)
    if best is None:
        return {
            "region": None, "tws_trend_cm_yr": None, "uncertainty_cm_yr": None,
            "provenance": base.provenance(
                "NASA GRACE / GRACE-FO", "JPL mascon RL06 terrestrial water storage", base.ACCESS_UNAVAILABLE,
                resolution_m=300_000, cadence="monthly", url="https://grace.jpl.nasa.gov/",
                note="No curated regional trend for this location. Check the GRACE layer on the map and local well records."),
        }
    region = best[1]
    return {
        "region": region["name"],
        "tws_trend_cm_yr": region["tws_trend_cm_yr"],
        "uncertainty_cm_yr": region["uncertainty_cm_yr"],
        "driver": region["driver"],
        "provenance": base.provenance(
            "NASA GRACE / GRACE-FO", "Regional terrestrial water storage trend (published mascon analyses)",
            base.ACCESS_CURATED, resolution_m=300_000, cadence="monthly", period="2002-2023",
            url="https://grace.jpl.nasa.gov/",
            note=("GRACE weighs water over ~300 km footprints. It shows whether the region is being "
                  "drawn down, not what is under one well. Confirm with local observation wells (USGS NWIS)."),
        ),
    }


# ----------------------------------------------------------------------- catalogue

MISSION_NOTES = [
    {"id": "smap", "mission": "SMAP", "measures": "Soil moisture and freeze/thaw", "native_resolution": "9-36 km, every 2-3 days",
     "fieldshift_use": "Drought onset, planting-moisture reliability, how often the root zone runs dry",
     "access": "Keyless subset where available, otherwise MERRA-2 root-zone wetness proxy via NASA POWER"},
    {"id": "gpm", "mission": "GPM IMERG", "measures": "Rain and snow rate", "native_resolution": "10 km, 30 min (daily totals used)",
     "fieldshift_use": "Storm intensity, erosive rain days, dry-spell length, rainfall reliability",
     "access": "Live and keyless through NASA POWER (IMERG_PRECTOT)"},
    {"id": "ecostress", "mission": "ECOSTRESS", "measures": "Land-surface temperature and evapotranspiration", "native_resolution": "70 m, irregular overpasses",
     "fieldshift_use": "Heat-stress hotspots, crop water demand",
     "access": "MODIS LST (1 km) and MOD16 ET (500 m) stand in; live and keyless"},
    {"id": "modis", "mission": "MODIS / VIIRS", "measures": "Vegetation greenness (NDVI/EVI)", "native_resolution": "250-500 m, 16-day",
     "fieldshift_use": "Bare-field months, green-up and harvest timing, crop stress",
     "access": "Live and keyless (ORNL DAAC subsets)"},
    {"id": "landsat", "mission": "Landsat / Sentinel-2", "measures": "Field-scale reflectance", "native_resolution": "10-30 m, 5-16 day",
     "fieldshift_use": "Reference scale for harmonisation; within-field variability",
     "access": "Not pulled live; named as the target grid and as an information gap"},
    {"id": "power", "mission": "NASA POWER", "measures": "Temperature, humidity, wind, sunshine", "native_resolution": "about 50 km, daily since 1981",
     "fieldshift_use": "Frost dates, heat days, growing degree days, reference ET",
     "access": "Live and keyless for any coordinate"},
    {"id": "grace", "mission": "GRACE / GRACE-FO", "measures": "Total water storage change", "native_resolution": "about 300 km, monthly",
     "fieldshift_use": "Whether the regional aquifer is being drawn down",
     "access": "Curated regional trends from published analyses"},
    {"id": "srtm", "mission": "SRTM", "measures": "Elevation", "native_resolution": "30 m, static",
     "fieldshift_use": "Slope steepness for runoff and erosion",
     "access": "Live and keyless (OpenTopoData mirror)"},
    {"id": "gedi", "mission": "GEDI", "measures": "Canopy height and woody biomass", "native_resolution": "1 km gridded",
     "fieldshift_use": "Windbreak and shelter context around the field",
     "access": "Map layer only (GIBS)"},
]
