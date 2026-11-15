"""Every dataset FieldShift draws on for Malaysian fields, and exactly how it is used.

The core stack follows the brief for a Malaysian adaptation:
    soil and crop suitability   FAO GAEZ + SMAP (soil moisture) + SRTM (slope and erosion), with
                                ISRIC SoilGrids for the soil profile itself
    weather and rainfall        NASA POWER + GPM IMERG, checked against MetMalaysia gauges
    crop health                 Copernicus Sentinel-2 (10 m NDVI)

status:
    live      pulled from the provider at request or build time, no key needed
    key       live when an optional key is set in .env, curated fallback otherwise
    curated   values assembled from published sources and shipped in data/
    proxy     a related NASA product stands in (stated wherever it is shown)
    map       shown as a NASA GIBS map layer only
    planned   named as an information gap and an extension point; not ingested yet
"""
from __future__ import annotations

SOURCES: list[dict] = [
    # ---- soil and crop suitability ------------------------------------------------------
    {"id": "gaez", "name": "FAO GAEZ v4", "agency": "FAO / IIASA", "group": "Soil and crop suitability", "status": "live",
     "use": "Suitability index (0-100) per crop for the field's 9 km cell, for 1981-2010 and for 2041-2070 under RCP8.5: a second opinion on the field-scale screen and a view of how suitability shifts with climate change.",
     "url": "https://gaez.fao.org/"},
    {"id": "smap", "name": "SMAP", "agency": "NASA", "group": "Soil and crop suitability", "status": "proxy",
     "use": "Root-zone wetness and drought months. SMAP L3 is read where the keyless ORNL subset holds it; MERRA-2 root-zone wetness (via POWER) stands in otherwise. SMAP L4 is a map layer.",
     "url": "https://earthdata.nasa.gov/data/platforms/space-based-platforms/smap"},
    {"id": "srtm", "name": "SRTM", "agency": "NASA", "group": "Soil and crop suitability", "status": "live",
     "use": "30 m elevation: slope for runoff and RUSLE erosion (critical for highland vegetable terraces), plus a map layer.",
     "url": "https://earthdata.nasa.gov/data/instruments/srtm"},
    {"id": "soilgrids", "name": "ISRIC SoilGrids 2.0", "agency": "ISRIC", "group": "Soil and crop suitability", "status": "live",
     "use": "250 m texture, organic carbon, bulk density, pH, CEC and water retention under the field; Ksat, erodibility and runoff group by pedotransfer functions.",
     "url": "https://soilgrids.org/"},
    {"id": "grace", "name": "GRACE / GRACE-FO", "agency": "NASA", "group": "Soil and crop suitability", "status": "map",
     "use": "Regional water-storage change as a map layer. No curated Malaysian trend is shipped; peninsular storage is dominated by monsoon swings rather than long-term depletion.",
     "url": "https://grace.jpl.nasa.gov/"},
    # ---- weather and rainfall -----------------------------------------------------------------
    {"id": "power", "name": "NASA POWER", "agency": "NASA", "group": "Weather and rainfall", "status": "live",
     "use": "24 years of daily temperature, humidity, wind and sunshine for any coordinate: heat days, growing degree days, reference ET, monsoon calendar.",
     "url": "https://power.larc.nasa.gov/"},
    {"id": "gpm", "name": "GPM IMERG", "agency": "NASA / JAXA", "group": "Weather and rainfall", "status": "live",
     "use": "Daily satellite rainfall: monsoon storm size, erosive rain days, flood months, and one of three sources in the fused rainfall estimate.",
     "url": "https://gpm.nasa.gov/data"},
    {"id": "ghcn", "name": "NOAA GHCN-Daily (MetMalaysia stations)", "agency": "NOAA NCEI / MetMalaysia", "group": "Weather and rainfall", "status": "live",
     "use": "Daily rain gauges at 16 Malaysian synoptic stations: the ground reference that sets the weight of each satellite product, discounted by distance to the field.",
     "url": "https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily"},
    {"id": "metmalaysia", "name": "MetMalaysia / JPS rain gauges", "agency": "Malaysian Meteorological Department / DID", "group": "Weather and rainfall", "status": "planned",
     "use": "The dense national gauge network (hundreds of JPS hydrological stations) would cut gauge distance to a few kilometres; it has no open API yet.",
     "url": "https://www.met.gov.my/"},
    {"id": "era5", "name": "ERA5", "agency": "ECMWF / Copernicus", "group": "Weather and rainfall", "status": "planned",
     "use": "Independent reanalysis for places far from a gauge; needs a Copernicus account.",
     "url": "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels"},
    # ---- crop health ---------------------------------------------------------------------------
    {"id": "sentinel2", "name": "Copernicus Sentinel-2", "agency": "ESA (via Microsoft Planetary Computer)", "group": "Crop health", "status": "live",
     "use": "10 m NDVI from every clear look since 2020: bare-field months, crop cycles per year (single vs double paddy), and a check on the assumed crop calendar.",
     "url": "https://planetarycomputer.microsoft.com/dataset/sentinel-2-l2a"},
    {"id": "modis", "name": "MODIS / VIIRS", "agency": "NASA", "group": "Crop health", "status": "live",
     "use": "250 m NDVI as a longer, coarser cross-check; land-surface temperature and ET (ECOSTRESS stand-ins). Also map layers.",
     "url": "https://lpdaac.usgs.gov/products/"},
    {"id": "ecostress", "name": "ECOSTRESS", "agency": "NASA", "group": "Crop health", "status": "proxy",
     "use": "Thermal stress. MODIS land-surface temperature (1 km) and MOD16 ET (500 m) stand in for the 70 m product.",
     "url": "https://ecostress.jpl.nasa.gov/data"},
    {"id": "landsat", "name": "Landsat", "agency": "NASA / USGS", "group": "Crop health", "status": "planned",
     "use": "30 m thermal and optical record back to the 1980s for long-term land-use change; not pulled yet.",
     "url": "https://earthexplorer.usgs.gov/"},
    {"id": "gedi", "name": "GEDI", "agency": "NASA", "group": "Crop health", "status": "map",
     "use": "Woody biomass around the field (forest edges, riparian strips, oil palm) as a map layer.", "url": "https://gedi.umd.edu/data"},
    # ---- crops and markets ----------------------------------------------------------------------
    {"id": "fama", "name": "FAMA price bulletins", "agency": "Federal Agricultural Marketing Authority", "group": "Crops and markets", "status": "curated",
     "use": "Multi-year average farm-gate prices and volatility per crop (RM).", "url": "https://www.fama.gov.my/"},
    {"id": "doa", "name": "DOA Malaysia crop statistics and budgets", "agency": "Department of Agriculture Malaysia", "group": "Crops and markets", "status": "curated",
     "use": "Reference yields and production costs per hectare (\"kos pengeluaran\"); local buyer notes per benchmark farm.",
     "url": "https://www.doa.gov.my/"},
    {"id": "mada", "name": "MADA / KADA / IADA scheme records", "agency": "Ministry of Agriculture and Food Security", "group": "Crops and markets", "status": "curated",
     "use": "Paddy season calendars, irrigation supply and average yields in the granary areas.",
     "url": "https://www.mada.gov.my/"},
    {"id": "mardi", "name": "MARDI recommendations", "agency": "Malaysian Agricultural Research and Development Institute", "group": "Crops and markets", "status": "curated",
     "use": "Crop durations, varieties and rotation trials used to set crop parameters (rice-maize, legume breaks, peat pineapple).",
     "url": "https://www.mardi.gov.my/"},
]
