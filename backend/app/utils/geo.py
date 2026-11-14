"""Geospatial and agro-meteorological helpers (pure Python, no GDAL required)."""
from __future__ import annotations

import math

DAYS_IN_MONTH = [31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MID_MONTH_DOY = [15, 46, 75, 106, 136, 167, 197, 228, 259, 289, 320, 350]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def offset_latlon(lat: float, lon: float, north_m: float, east_m: float) -> tuple[float, float]:
    dlat = north_m / 111_320.0
    dlon = east_m / (111_320.0 * max(0.05, math.cos(math.radians(lat))))
    return lat + dlat, lon + dlon


def extraterrestrial_radiation_mm(lat: float, doy: int) -> float:
    """Daily extraterrestrial radiation Ra expressed as mm/day of evaporation (FAO-56 eq. 21)."""
    phi = math.radians(lat)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    delta = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    x = max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta)))
    ws = math.acos(x)
    ra_mj = (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(ws)
    )
    return max(0.0, ra_mj * 0.408)


def hargreaves_et0_mm_day(lat: float, doy: int, tmax: float, tmin: float) -> float:
    """Hargreaves-Samani reference ET (mm/day). Needs only temperature, so it works anywhere
    NASA POWER does and responds transparently to a warming scenario."""
    tmean = (tmax + tmin) / 2.0
    spread = max(0.0, tmax - tmin)
    ra = extraterrestrial_radiation_mm(lat, doy)
    return max(0.0, 0.0023 * ra * (tmean + 17.8) * math.sqrt(spread))


def slope_from_grid(z: list[list[float]], cell_m: float) -> dict:
    """Horn (1981) slope/aspect from a 3x3 elevation window (row 0 = north)."""
    (a, b, c), (d, _e, f), (g, h, i) = z
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * cell_m)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * cell_m)
    rise = math.sqrt(dzdx**2 + dzdy**2)
    aspect = (math.degrees(math.atan2(dzdy, -dzdx)) + 360) % 360
    flat = [v for row in z for v in row]
    return {
        "slope_pct": rise * 100.0,
        "aspect_deg": (450 - aspect) % 360,
        "relief_m": max(flat) - min(flat),
    }


def ls_factor(slope_pct: float, slope_length_m: float) -> float:
    """RUSLE topographic factor (McCool et al. 1987/1989)."""
    theta = math.atan(slope_pct / 100.0)
    sin_t = math.sin(theta)
    s = 10.8 * sin_t + 0.03 if slope_pct < 9 else 16.8 * sin_t - 0.50
    beta = (sin_t / 0.0896) / (3.0 * sin_t**0.8 + 0.56)
    m = beta / (1 + beta)
    return max(0.03, (slope_length_m / 22.13) ** m * s)


def albers_conus(lat: float, lon: float) -> tuple[float, float]:
    """WGS84 lat/lon -> USA Contiguous Albers Equal Area (EPSG:5070), used by CropScape."""
    a, e = 6378137.0, 0.0818191910428158
    phi1, phi2, phi0, lam0 = map(math.radians, (29.5, 45.5, 23.0, -96.0))

    def q(phi: float) -> float:
        s = math.sin(phi)
        return (1 - e**2) * (s / (1 - e**2 * s**2) - (1 / (2 * e)) * math.log((1 - e * s) / (1 + e * s)))

    def m(phi: float) -> float:
        return math.cos(phi) / math.sqrt(1 - e**2 * math.sin(phi) ** 2)

    n = (m(phi1) ** 2 - m(phi2) ** 2) / (q(phi2) - q(phi1))
    c = m(phi1) ** 2 + n * q(phi1)
    rho0 = a * math.sqrt(c - n * q(phi0)) / n
    rho = a * math.sqrt(c - n * q(math.radians(lat))) / n
    theta = n * (math.radians(lon) - lam0)
    return rho * math.sin(theta), rho0 - rho * math.cos(theta)


def usda_texture_class(sand: float, silt: float, clay: float) -> str:
    """USDA soil textural triangle."""
    if silt + 1.5 * clay < 15:
        return "sand"
    if silt + 2 * clay < 30:
        return "loamy sand"
    if (7 <= clay < 20 and sand > 52 and silt + 2 * clay >= 30) or (clay < 7 and silt < 50 and silt + 2 * clay >= 30):
        return "sandy loam"
    if 7 <= clay < 27 and 28 <= silt < 50 and sand <= 52:
        return "loam"
    if (silt >= 50 and 12 <= clay < 27) or (50 <= silt < 80 and clay < 12):
        return "silt loam"
    if silt >= 80 and clay < 12:
        return "silt"
    if 20 <= clay < 35 and silt < 28 and sand > 45:
        return "sandy clay loam"
    if 27 <= clay < 40 and 20 < sand <= 45:
        return "clay loam"
    if 27 <= clay < 40 and sand <= 20:
        return "silty clay loam"
    if clay >= 35 and sand > 45:
        return "sandy clay"
    if clay >= 40 and silt >= 40:
        return "silty clay"
    if clay >= 40:
        return "clay"
    return "loam"
