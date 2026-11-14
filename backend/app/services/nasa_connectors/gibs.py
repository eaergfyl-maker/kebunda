"""NASA GIBS / Worldview WMTS layer catalogue served to the map.

Identifiers, tile matrix sets and formats were checked against the live
WMTSCapabilities document (EPSG:3857 "best" endpoint). `check_live()` re-validates them
on demand so the map can grey out a layer GIBS has retired.
"""
from __future__ import annotations

import re

from app.services.nasa_connectors import base

GIBS_BASE = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best"
CAPABILITIES_URL = f"{GIBS_BASE}/1.0.0/WMTSCapabilities.xml"
TILE_TEMPLATE = GIBS_BASE + "/{layer}/default/{time}/{tms}/{z}/{y}/{x}.{ext}"

# temporal: "daily" | "monthly" | "yearly" | "static"
LAYERS: list[dict] = [
    {
        "id": "MODIS_Terra_CorrectedReflectance_TrueColor", "title": "True colour (MODIS Terra)",
        "group": "imagery", "mission": "MODIS", "tms": "GoogleMapsCompatible_Level9", "ext": "jpg",
        "temporal": "daily", "start": "2000-02-24", "end": None, "max_zoom": 9, "resolution_m": 250,
        "plain": "What the land looked like from space on the chosen day.",
        "legend": None,
    },
    {
        "id": "MODIS_Terra_L3_NDVI_Monthly", "title": "Vegetation greenness (NDVI)",
        "group": "vegetation", "mission": "MODIS", "tms": "GoogleMapsCompatible_Level7", "ext": "png",
        "temporal": "monthly", "start": "2000-03-01", "end": None, "max_zoom": 7, "resolution_m": 1000,
        "plain": "Green means living plant cover. Tan means bare or dormant ground.",
        "legend": {"unit": "NDVI", "stops": [[0.0, "#a6611a"], [0.2, "#dfc27d"], [0.4, "#c7e9ad"], [0.6, "#66bd63"], [0.9, "#00441b"]]},
    },
    {
        "id": "SMAP_L4_Analyzed_Root_Zone_Soil_Moisture", "title": "Root-zone soil moisture (SMAP L4)",
        "group": "water", "mission": "SMAP", "tms": "GoogleMapsCompatible_Level6", "ext": "png",
        "temporal": "daily", "start": "2015-03-31", "end": None, "max_zoom": 6, "resolution_m": 9000,
        "plain": "How much water is in the top metre of soil. Each pixel is about 9 km wide.",
        "legend": {"unit": "m3/m3", "stops": [[0.0, "#8c510a"], [0.15, "#d8b365"], [0.3, "#c7eae5"], [0.45, "#5ab4ac"], [0.6, "#01665e"]]},
    },
    {
        "id": "IMERG_Precipitation_Rate", "title": "Rainfall rate (GPM IMERG)",
        "group": "water", "mission": "GPM", "tms": "GoogleMapsCompatible_Level6", "ext": "png",
        "temporal": "daily", "start": "2000-06-01", "end": None, "max_zoom": 6, "resolution_m": 10000,
        "plain": "Where and how hard it rained that day, measured from orbit.",
        "legend": {"unit": "mm/hr", "stops": [[0.1, "#c6dbef"], [1, "#6baed6"], [5, "#2171b5"], [15, "#f0c929"], [40, "#d7301f"]]},
    },
    {
        "id": "MODIS_Terra_Land_Surface_Temp_Day", "title": "Daytime ground temperature (MODIS LST)",
        "group": "heat", "mission": "MODIS", "tms": "GoogleMapsCompatible_Level7", "ext": "png",
        "temporal": "daily", "start": "2000-02-24", "end": None, "max_zoom": 7, "resolution_m": 1000,
        "plain": "How hot the ground surface was. Bare, dry soil runs much hotter than a green canopy.",
        "legend": {"unit": "deg C", "stops": [[-10, "#313695"], [5, "#74add1"], [20, "#fee090"], [35, "#f46d43"], [50, "#a50026"]]},
    },
    {
        "id": "GRACE_Tellus_Liquid_Water_Equivalent_Thickness_Mascon_CRI", "title": "Total water storage change (GRACE)",
        "group": "water", "mission": "GRACE / GRACE-FO", "tms": "GoogleMapsCompatible_Level6", "ext": "png",
        "temporal": "monthly", "start": "2002-04-01", "end": "2022-07-01", "max_zoom": 6, "resolution_m": 300000,
        "plain": "Whether a whole region is gaining or losing water, including deep groundwater. Pixels are about 300 km wide.",
        "legend": {"unit": "cm water", "stops": [[-25, "#8c2d04"], [-10, "#f1a340"], [0, "#f7f7f7"], [10, "#92c5de"], [25, "#2166ac"]]},
    },
    {
        "id": "GLDAS_Underground_Soil_Moisture_Monthly", "title": "Deep soil moisture (GLDAS)",
        "group": "water", "mission": "GLDAS", "tms": "GoogleMapsCompatible_Level6", "ext": "png",
        "temporal": "monthly", "start": "2000-04-01", "end": None, "max_zoom": 6, "resolution_m": 28000,
        "plain": "Modelled soil water below the surface, month by month, back to 2000.",
        "legend": {"unit": "kg/m2", "stops": [[0, "#8c510a"], [200, "#d8b365"], [400, "#c7eae5"], [700, "#01665e"]]},
    },
    {
        "id": "SRTM_Color_Index", "title": "Elevation (SRTM)",
        "group": "terrain", "mission": "SRTM", "tms": "GoogleMapsCompatible_Level12", "ext": "png",
        "temporal": "static", "start": None, "end": None, "max_zoom": 12, "resolution_m": 30,
        "plain": "Height of the land. Water runs from the high colours to the low ones.",
        "legend": {"unit": "m", "stops": [[0, "#1a9850"], [500, "#d9ef8b"], [1500, "#fdae61"], [3000, "#a6611a"], [5000, "#f7f7f7"]]},
    },
    {
        "id": "ASTER_GDEM_Greyscale_Shaded_Relief", "title": "Shaded relief (ASTER GDEM)",
        "group": "terrain", "mission": "ASTER", "tms": "GoogleMapsCompatible_Level12", "ext": "jpg",
        "temporal": "static", "start": None, "end": None, "max_zoom": 12, "resolution_m": 30,
        "plain": "Hills and draws drawn as light and shadow, to spot slopes that shed water.",
        "legend": None,
    },
    {
        "id": "GEDI_ISS_L4B_Aboveground_Biomass_Density_Mean_201904-202303", "title": "Tree and shrub biomass (GEDI)",
        "group": "landscape", "mission": "GEDI", "tms": "GoogleMapsCompatible_Level7", "ext": "png",
        "temporal": "static", "start": "2019-04-18", "end": "2019-04-18", "max_zoom": 7, "resolution_m": 1000,
        "plain": "Woody plant mass around the farm: windbreaks, riparian strips and woodlots.",
        "legend": {"unit": "Mg/ha", "stops": [[0, "#f7fcb9"], [50, "#addd8e"], [150, "#31a354"], [300, "#004529"]]},
    },
    {
        "id": "MODIS_Combined_L3_IGBP_Land_Cover_Type_Annual", "title": "Land cover type (MODIS)",
        "group": "landscape", "mission": "MODIS", "tms": "GoogleMapsCompatible_Level8", "ext": "png",
        "temporal": "yearly", "start": "2001-01-01", "end": "2024-01-01", "max_zoom": 8, "resolution_m": 500,
        "plain": "Cropland, grassland, forest, water and towns around the field.",
        "legend": None,
    },
]


def catalogue() -> list[dict]:
    """Layer metadata with a ready-to-use XYZ tile template for each layer."""
    out = []
    for layer in LAYERS:
        template = (
            TILE_TEMPLATE.replace("{layer}", layer["id"])
            .replace("{tms}", layer["tms"])
            .replace("{ext}", layer["ext"])
        )
        if layer["temporal"] == "static" and not layer["start"]:
            template = template.replace("/{time}", "")
        out.append({**layer, "tile_url": template, "attribution": "NASA EOSDIS GIBS"})
    return out


def check_live() -> dict:
    """Confirm which catalogue identifiers GIBS currently advertises."""
    try:
        xml, access = base.fetch("gibs-capabilities", CAPABILITIES_URL, as_text=True, ttl_hours=24, timeout_s=120)
    except base.ConnectorError as exc:
        return {"checked": False, "reason": str(exc), "layers": {}}
    advertised = set(re.findall(r"<ows:Identifier>([^<]+)</ows:Identifier>", xml))
    return {
        "checked": True,
        "access": access,
        "layers": {layer["id"]: layer["id"] in advertised for layer in LAYERS},
    }
