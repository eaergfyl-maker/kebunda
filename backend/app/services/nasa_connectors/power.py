"""NASA POWER (Prediction Of Worldwide Energy Resources) daily point client.

Keyless, global, any coordinate. One request returns 24 years of daily agro-meteorology
from MERRA-2 (~50 km) plus GPM IMERG precipitation (~10 km), which is why POWER is the
backbone for custom fields.

Docs: https://power.larc.nasa.gov/docs/services/api/temporal/daily/
"""
from __future__ import annotations

from app.config import CLIMATE_END_YEAR, CLIMATE_START_YEAR
from app.services.nasa_connectors import base

POWER_DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

# POWER parameter -> (our key, plain-language meaning)
PARAMETERS = {
    "T2M_MAX": ("tmax", "Daily maximum air temperature at 2 m (deg C)"),
    "T2M_MIN": ("tmin", "Daily minimum air temperature at 2 m (deg C)"),
    "PRECTOTCORR": ("precip", "Bias-corrected MERRA-2 precipitation (mm/day)"),
    "IMERG_PRECTOT": ("precip_imerg", "GPM IMERG satellite precipitation (mm/day)"),
    "GWETROOT": ("wet_root", "Root-zone soil wetness, 0 = dry to 1 = saturated"),
    "GWETTOP": ("wet_top", "Surface (0-5 cm) soil wetness, 0-1"),
    "ALLSKY_SFC_SW_DWN": ("solar", "Solar radiation at the surface (MJ/m2/day)"),
    "RH2M": ("rh", "Relative humidity at 2 m (%)"),
    "WS2M": ("wind", "Wind speed at 2 m (m/s)"),
    "TS": ("tskin", "Earth skin temperature (deg C)"),
}
FILL = -999.0


def fetch_daily(
    lat: float,
    lon: float,
    start_year: int = CLIMATE_START_YEAR,
    end_year: int = CLIMATE_END_YEAR,
) -> dict:
    """Return {"dates": ["YYYYMMDD", ...], "series": {key: [float|None, ...]}, "provenance": {...}}."""
    params = {
        "parameters": ",".join(PARAMETERS),
        "community": "AG",
        "longitude": round(lon, 4),
        "latitude": round(lat, 4),
        "start": f"{start_year}0101",
        "end": f"{end_year}1231",
        "format": "JSON",
        # IMERG is only served on the UTC time standard.
        "time-standard": "UTC",
    }
    payload, access = base.fetch("power-daily", POWER_DAILY_URL, params=params, timeout_s=90)
    return parse_daily(payload, access, start_year, end_year)


def parse_daily(payload: dict, access: str, start_year: int, end_year: int) -> dict:
    try:
        raw = payload["properties"]["parameter"]
    except (KeyError, TypeError) as exc:
        raise base.ConnectorError(f"unexpected NASA POWER payload: {exc}") from exc
    dates = sorted(next(iter(raw.values())).keys())
    series: dict[str, list[float | None]] = {}
    for power_name, (key, _desc) in PARAMETERS.items():
        column = raw.get(power_name, {})
        series[key] = [
            None if (v := column.get(d)) is None or v <= FILL + 1 else float(v) for d in dates
        ]
    elevation = None
    try:
        elevation = float(payload["geometry"]["coordinates"][2])
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return {
        "dates": dates,
        "series": series,
        "grid_elevation_m": elevation,
        "provenance": base.provenance(
            "NASA POWER",
            "MERRA-2 meteorology + GPM IMERG precipitation (daily, point)",
            access,
            resolution_m=55_000,
            cadence="daily",
            period=f"{start_year}-{end_year}",
            url="https://power.larc.nasa.gov/",
            note="MERRA-2 cells are ~0.5 x 0.625 deg; IMERG is 0.1 deg (~10 km).",
        ),
    }
