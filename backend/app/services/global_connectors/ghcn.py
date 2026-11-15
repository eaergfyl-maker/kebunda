"""Ground-truth rain gauges: NOAA GHCN-Daily at Malaysian Meteorological Department stations.

GHCN-Daily carries the synoptic records of 16 MetMalaysia stations with daily rainfall
since the 1950s. The connector picks the nearest station to a field and returns its daily
rain and temperature in the same shape the satellite comparison expects. A gauge tens of
kilometres away is still ground truth for the region, not for the field, so the distance
is carried into the provenance (`resolution_m`) and lowers the gauge's weight in fusion.

API: https://www.ncei.noaa.gov/access/services/data/v1 (keyless)
"""
from __future__ import annotations

from app.services.nasa_connectors import base
from app.utils.geo import haversine_km

NCEI_URL = "https://www.ncei.noaa.gov/access/services/data/v1"
MAX_DISTANCE_KM = 150.0

# From ghcnd-stations.txt / ghcnd-inventory.txt (stations with PRCP into 2022 or later).
STATIONS = [
    {"id": "MY000048620", "name": "Sitiawan", "lat": 4.217, "lon": 100.700, "elev_m": 8},
    {"id": "MY000048657", "name": "Kuantan", "lat": 3.620, "lon": 103.220, "elev_m": 16},
    {"id": "MY000096413", "name": "Kuching", "lat": 1.483, "lon": 110.333, "elev_m": 27},
    {"id": "MY000096441", "name": "Bintulu", "lat": 3.200, "lon": 113.033, "elev_m": 5},
    {"id": "MY000096465", "name": "Labuan", "lat": 5.300, "lon": 115.250, "elev_m": 30},
    {"id": "MY000096491", "name": "Sandakan", "lat": 5.900, "lon": 118.067, "elev_m": 13},
    {"id": "MYM00048601", "name": "Penang International", "lat": 5.297, "lon": 100.277, "elev_m": 3},
    {"id": "MYM00048615", "name": "Kota Bharu (Sultan Ismail Petra)", "lat": 6.167, "lon": 102.293, "elev_m": 5},
    {"id": "MYM00048647", "name": "Subang (Sultan Abdul Aziz Shah)", "lat": 3.131, "lon": 101.549, "elev_m": 27},
    {"id": "MYM00048650", "name": "KLIA Sepang", "lat": 2.746, "lon": 101.710, "elev_m": 21},
    {"id": "MYM00048665", "name": "Melaka", "lat": 2.263, "lon": 102.252, "elev_m": 11},
    {"id": "MYM00048674", "name": "Mersing", "lat": 2.450, "lon": 103.833, "elev_m": 45},
    {"id": "MYM00096421", "name": "Sibu", "lat": 2.262, "lon": 111.985, "elev_m": 37},
    {"id": "MYM00096449", "name": "Miri", "lat": 4.322, "lon": 113.987, "elev_m": 18},
    {"id": "MYM00096471", "name": "Kota Kinabalu", "lat": 5.937, "lon": 116.051, "elev_m": 3},
    {"id": "MYM00096481", "name": "Tawau", "lat": 4.313, "lon": 118.122, "elev_m": 17},
]


def nearest_station(lat: float, lon: float) -> tuple[dict, float] | None:
    best = min(((s, haversine_km(lat, lon, s["lat"], s["lon"])) for s in STATIONS), key=lambda x: x[1])
    return best if best[1] <= MAX_DISTANCE_KM else None


def fetch_gauge(lat: float, lon: float, start_year: int, end_year: int) -> dict:
    """Return {"dates": ["YYYYMMDD"], "series": {"precip", "tmax", "tmin"}, "station": {...}, "provenance": {...}}."""
    hit = nearest_station(lat, lon)
    if hit is None:
        raise base.ConnectorError(f"no GHCN-Daily gauge within {MAX_DISTANCE_KM:.0f} km")
    station, dist = hit
    rows, access = base.fetch("ghcn", NCEI_URL, params={
        "dataset": "daily-summaries", "stations": station["id"], "dataTypes": "PRCP,TMAX,TMIN",
        "startDate": f"{start_year}-01-01", "endDate": f"{end_year}-12-31", "format": "json", "units": "metric",
    }, timeout_s=120)
    return parse_ghcn(rows, access, station, dist)


def parse_ghcn(rows: list[dict], access: str, station: dict, distance_km: float) -> dict:
    if not isinstance(rows, list) or not rows:
        raise base.ConnectorError("GHCN-Daily returned no records for the station")

    def num(row: dict, key: str) -> float | None:
        try:
            return float(row[key])
        except (KeyError, TypeError, ValueError):
            return None

    rows = sorted(rows, key=lambda r: r.get("DATE", ""))
    dates = [r["DATE"].replace("-", "") for r in rows if r.get("DATE")]
    series = {"precip": [num(r, "PRCP") for r in rows if r.get("DATE")],
              "tmax": [num(r, "TMAX") for r in rows if r.get("DATE")],
              "tmin": [num(r, "TMIN") for r in rows if r.get("DATE")]}
    covered = sum(1 for v in series["precip"] if v is not None)
    return {
        "dates": dates,
        "series": series,
        "station": {**station, "distance_km": round(distance_km, 1), "rain_days_reported": covered},
        "provenance": base.provenance(
            "NOAA NCEI GHCN-Daily (MetMalaysia station)", f"Daily rain gauge: {station['name']} ({station['id']})", access,
            resolution_m=max(1000.0, distance_km * 1000.0), cadence="daily",
            url="https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily",
            note=(f"The gauge is {distance_km:.0f} km from the field. Tropical storms are a few kilometres wide, so daily "
                  "totals differ a lot between the gauge and the field; monthly and seasonal totals agree far better. "
                  "Days the station did not report are left out, not counted as dry."),
        ),
    }
