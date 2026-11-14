"""Ground-based reference weather: Daymet (station-interpolated, 1 km, keyless).

Daymet is built from rain gauges and thermometers (GHCN, SNOTEL, CoCoRaHS-class stations)
interpolated with terrain, so it is the "ground truth" side of the satellite-vs-ground
comparison. CoCoRaHS and PRISM are the natural next sources; they are listed as extension
points in docs/architecture.
"""
from __future__ import annotations

import datetime as dt

from app.services.nasa_connectors import base

DAYMET_URL = "https://daymet.ornl.gov/single-pixel/api/data"


def fetch_daymet(lat: float, lon: float, start_year: int, end_year: int) -> dict:
    """Return {"dates": ["YYYYMMDD"], "series": {"precip": [...], "tmax": [...], "tmin": [...]}}."""
    text, access = base.fetch(
        "daymet", DAYMET_URL,
        params={"lat": round(lat, 5), "lon": round(lon, 5), "vars": "prcp,tmax,tmin",
                "start": f"{start_year}-01-01", "end": f"{end_year}-12-31"},
        as_text=True, timeout_s=90,
    )
    return parse_daymet(text, access)


def parse_daymet(text: str, access: str) -> dict:
    lines = text.splitlines()
    try:
        header_idx = next(i for i, line in enumerate(lines) if line.startswith("year,yday"))
    except StopIteration as exc:
        raise base.ConnectorError("unexpected Daymet payload") from exc
    cols = [c.split(" ")[0] for c in lines[header_idx].split(",")]
    dates: list[str] = []
    series: dict[str, list[float | None]] = {"precip": [], "tmax": [], "tmin": []}
    rename = {"prcp": "precip", "tmax": "tmax", "tmin": "tmin"}
    for line in lines[header_idx + 1:]:
        parts = line.split(",")
        if len(parts) < len(cols):
            continue
        row = dict(zip(cols, parts))
        day = dt.date(int(float(row["year"])), 1, 1) + dt.timedelta(days=int(float(row["yday"])) - 1)
        dates.append(day.strftime("%Y%m%d"))
        for src, dst in rename.items():
            try:
                series[dst].append(float(row[src]))
            except (KeyError, ValueError):
                series[dst].append(None)
    return {
        "dates": dates,
        "series": series,
        "provenance": base.provenance(
            "ORNL DAAC Daymet v4", "Station-interpolated daily weather (ground reference)", access,
            resolution_m=1000, cadence="daily", url="https://daymet.ornl.gov/",
            note="Interpolated from gauges, so a field between stations still carries interpolation error.",
        ),
    }
