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

# Regional total-water-storage trends (cm of water per year) from published GRACE / GRACE-FO
# mascon analyses. GRACE resolves ~300 km, so one number covers a region. No Malaysian region is
# curated: published analyses show storage over Peninsular Malaysia and Borneo dominated by
# monsoon and ENSO swings rather than a clear long-term trend, so Kebunda shows the GRACE map
# layer and reports the trend as an information gap instead of inventing one.
GRACE_REGIONS: list[dict] = []


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
                note=("No curated regional trend for this location. In Malaysia storage swings with the monsoons and ENSO; "
                      "check the GRACE layer on the map and JPS river and reservoir records.")),
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
                  "drawn down, not what is under one well. Confirm with local water-level records."),
        ),
    }


# ----------------------------------------------------------------------- catalogue

MISSION_NOTES = [
    {"id": "smap", "mission": "SMAP", "measures": "Soil moisture and freeze/thaw", "native_resolution": "9-36 km, every 2-3 days",
     "kebunda_use": "Dry-spell onset between monsoons, planting-moisture reliability, how often the root zone runs dry",
     "access": "Keyless subset where available, otherwise MERRA-2 root-zone wetness proxy via NASA POWER"},
    {"id": "gpm", "mission": "GPM IMERG", "measures": "Rain and snow rate", "native_resolution": "10 km, 30 min (daily totals used)",
     "kebunda_use": "Monsoon storm intensity, erosive rain days, flood months, dry-spell length",
     "access": "Live and keyless through NASA POWER (IMERG_PRECTOT)"},
    {"id": "ecostress", "mission": "ECOSTRESS", "measures": "Land-surface temperature and evapotranspiration", "native_resolution": "70 m, irregular overpasses",
     "kebunda_use": "Heat-stress hotspots, crop water demand",
     "access": "MODIS LST (1 km) and MOD16 ET (500 m) stand in; live and keyless"},
    {"id": "modis", "mission": "MODIS / VIIRS", "measures": "Vegetation greenness (NDVI/EVI)", "native_resolution": "250-500 m, 16-day",
     "kebunda_use": "Bare-field months, green-up and harvest timing, crop stress",
     "access": "Live and keyless (ORNL DAAC subsets)"},
    {"id": "sentinel2", "mission": "Copernicus Sentinel-2", "measures": "Field-scale greenness (NDVI)", "native_resolution": "10 m, 5-day",
     "kebunda_use": "Crop cycles per year, bare months, crop-calendar check on smallholder plots",
     "access": "Live and keyless (Microsoft Planetary Computer STAC + point reads)"},
    {"id": "power", "mission": "NASA POWER", "measures": "Temperature, humidity, wind, sunshine", "native_resolution": "about 50 km, daily since 1981",
     "kebunda_use": "Heat days, growing degree days, reference ET, the monsoon calendar",
     "access": "Live and keyless for any coordinate"},
    {"id": "grace", "mission": "GRACE / GRACE-FO", "measures": "Total water storage change", "native_resolution": "about 300 km, monthly",
     "kebunda_use": "Whether the regional aquifer is being drawn down",
     "access": "Map layer; no curated Malaysian trend"},
    {"id": "srtm", "mission": "SRTM", "measures": "Elevation", "native_resolution": "30 m, static",
     "kebunda_use": "Slope steepness for runoff and erosion, highland terraces",
     "access": "Live and keyless (OpenTopoData mirror)"},
    {"id": "gedi", "mission": "GEDI", "measures": "Canopy height and woody biomass", "native_resolution": "1 km gridded",
     "kebunda_use": "Forest edges, riparian strips and plantation canopy around the field",
     "access": "Map layer only (GIBS)"},
]
