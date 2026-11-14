"""Temporal harmonisation: collapse daily / 8-day / 16-day records onto one monthly grid.

Every sensor reports on its own clock (POWER daily, MODIS LST 8-day, NDVI 16-day). The
engines all run on a common calendar-month step, so this module is where "temporal
resampling to a common grid" happens. Extremes that monthly means would hide (erosive rain
days, frost days, heat days, daily variability) are counted from the daily record first.
"""
from __future__ import annotations

import math
from collections import defaultdict

from app.utils.geo import DAYS_IN_MONTH, MID_MONTH_DOY, hargreaves_et0_mm_day
from app.utils.stats import mean, pearson, percentile, r, stdev, theil_sen

EROSIVE_MM = 12.7  # RUSLE convention: storms under 0.5 in are not counted as erosive
WET_DAY_MM = 1.0


def _month_buckets(dates: list[str], values: list[float | None]) -> dict[tuple[int, int], list[float]]:
    out: dict[tuple[int, int], list[float]] = defaultdict(list)
    for d, v in zip(dates, values):
        if v is not None:
            out[(int(d[:4]), int(d[4:6]) - 1)].append(v)
    return out


def summarise_daily(power: dict, lat: float) -> dict:
    """Turn a NASA POWER daily record into monthly normals, extremes, year-by-month series and trends."""
    dates, s = power["dates"], power["series"]
    years = sorted({int(d[:4]) for d in dates})
    b = {k: _month_buckets(dates, v) for k, v in s.items()}

    def grid(fn) -> list[list[float | None]]:
        return [[fn(y, m) for m in range(12)] for y in years]

    def col_mean(g: list[list[float | None]]) -> list[float]:
        return [mean([row[m] for row in g]) for m in range(12)]

    def tot(key: str, y: int, m: int) -> float | None:
        vals = b[key].get((y, m))
        if not vals:
            return None
        return sum(vals) * DAYS_IN_MONTH[m] / len(vals)  # gap-robust monthly total

    def avg(key: str, y: int, m: int) -> float | None:
        vals = b[key].get((y, m))
        return sum(vals) / len(vals) if vals else None

    def count(key: str, y: int, m: int, pred) -> float | None:
        vals = b[key].get((y, m))
        if not vals:
            return None
        return sum(1 for v in vals if pred(v)) * DAYS_IN_MONTH[m] / len(vals)

    g_precip = grid(lambda y, m: tot("precip", y, m))
    g_imerg = grid(lambda y, m: tot("precip_imerg", y, m))
    g_tmax = grid(lambda y, m: avg("tmax", y, m))
    g_tmin = grid(lambda y, m: avg("tmin", y, m))
    g_tmean = [[None if a is None or c is None else (a + c) / 2 for a, c in zip(ra, rc)] for ra, rc in zip(g_tmax, g_tmin)]
    g_wet = grid(lambda y, m: avg("wet_root", y, m))
    g_wet_top = grid(lambda y, m: avg("wet_top", y, m))
    g_frost = grid(lambda y, m: count("tmin", y, m, lambda v: v < 0.0))
    g_heat35 = grid(lambda y, m: count("tmax", y, m, lambda v: v >= 35.0))
    g_heat32 = grid(lambda y, m: count("tmax", y, m, lambda v: v >= 32.0))
    g_wetdays = grid(lambda y, m: count("precip", y, m, lambda v: v >= WET_DAY_MM))
    g_erosive = grid(lambda y, m: count("precip", y, m, lambda v: v >= EROSIVE_MM))
    # erosivity proxy: storm energy rises faster than depth (Richardson et al. 1983, EI ~ P^1.81)
    g_ei = grid(lambda y, m: sum(v**1.81 for v in b["precip"].get((y, m), []) if v >= EROSIVE_MM))
    g_et0 = [
        [None if tx is None or tn is None else hargreaves_et0_mm_day(lat, MID_MONTH_DOY[m], tx, tn) * DAYS_IN_MONTH[m]
         for m, (tx, tn) in enumerate(zip(rx, rn))]
        for rx, rn in zip(g_tmax, g_tmin)
    ]

    # pooled within-month daily spread, used to shift frost/heat-day counts under scenarios
    def pooled_sd(key: str, m: int) -> float:
        dev = []
        for y in years:
            vals = b[key].get((y, m))
            if vals and len(vals) > 3:
                mu = sum(vals) / len(vals)
                dev.extend(v - mu for v in vals)
        return math.sqrt(sum(d * d for d in dev) / len(dev)) if dev else 4.0

    def daily_pool(key: str, m: int) -> list[float]:
        return [v for y in years for v in b[key].get((y, m), [])]

    wet_pool = [[v for v in daily_pool("precip", m) if v >= WET_DAY_MM] for m in range(12)]
    ei_norm = col_mean(g_ei)
    ei_total = sum(ei_norm) or 1.0
    rh = col_mean(grid(lambda y, m: avg("rh", y, m)))
    tmean_n = col_mean(g_tmean)
    vpd = [0.6108 * math.exp(17.27 * t / (t + 237.3)) * (1 - h / 100.0) for t, h in zip(tmean_n, rh)]

    monthly = {
        "tmean": col_mean(g_tmean), "tmax": col_mean(g_tmax), "tmin": col_mean(g_tmin),
        "tmax_sd": [pooled_sd("tmax", m) for m in range(12)],
        "tmin_sd": [pooled_sd("tmin", m) for m in range(12)],
        "precip": col_mean(g_precip), "precip_imerg": col_mean(g_imerg),
        "et0": col_mean(g_et0),
        "wet_root": col_mean(g_wet), "wet_top": col_mean(g_wet_top),
        "solar": col_mean(grid(lambda y, m: avg("solar", y, m))),
        "rh": rh, "vpd_kpa": vpd,
        "wind": col_mean(grid(lambda y, m: avg("wind", y, m))),
        "tskin": col_mean(grid(lambda y, m: avg("tskin", y, m))),
        "wet_days": col_mean(g_wetdays),
        "wet_day_mean_mm": [mean(p, 5.0) for p in wet_pool],
        "p95_daily_mm": [percentile(p, 95, 0.0) for p in wet_pool],
        "max_1day_mm": [max(p) if p else 0.0 for p in wet_pool],
        "erosive_days": col_mean(g_erosive),
        "erosivity_share": [v / ei_total for v in ei_norm],
        "frost_days": col_mean(g_frost),
        "heat_days_32": col_mean(g_heat32),
        "heat_days_35": col_mean(g_heat35),
    }
    monthly = {k: [r(v, 3) for v in vals] for k, vals in monthly.items()}

    frost = _frost_dates(dates, s["tmin"], years, lat)

    def annual(g: list[list[float | None]], how: str, months: range = range(12)) -> list[float | None]:
        out = []
        for row in g:
            vals = [row[m] for m in months if row[m] is not None]
            if len(vals) < len(months) * 0.75:
                out.append(None)
            else:
                out.append(sum(vals) if how == "sum" else sum(vals) / len(vals))
        return out

    warm = range(3, 9) if lat >= 0 else [9, 10, 11, 0, 1, 2]
    annual_series = {
        "precip_mm": annual(g_precip, "sum"),
        "warm_season_precip_mm": annual(g_precip, "sum", warm),
        "tmean_c": annual(g_tmean, "mean"),
        "heat_days_35": annual(g_heat35, "sum"),
        "frost_days": annual(g_frost, "sum"),
        "erosive_days": annual(g_erosive, "sum"),
        "wet_root": annual(g_wet, "mean"),
        "warm_season_wet_root": annual(g_wet, "mean", warm),
        "et0_mm": annual(g_et0, "sum"),
        "max_1day_mm": [max((v for m in range(12) for v in b["precip"].get((y, m), [])), default=None) for y in years],
    }
    trends = {}
    for key, vals in annual_series.items():
        t = theil_sen(years, vals)
        trends[key] = {"per_decade": r(t["slope"] * 10, 3), "p_value": t["p_value"], "significant": t["significant"]}

    # standardised root-zone wetness anomaly: the drought signal (z < -1 = notably dry month)
    anomalies = []
    for m in range(12):
        col = [row[m] for row in g_wet]
        mu, sd = mean(col), stdev(col) or 1e-6
        for yi, v in enumerate(col):
            anomalies.append((yi, m, None if v is None else (v - mu) / sd))
    anomalies.sort()
    z_grid = [[None] * 12 for _ in years]
    for yi, m, z in anomalies:
        z_grid[yi][m] = r(z, 2)
    drought_months = [sum(1 for z in row if z is not None and z <= -1.0) for row in z_grid]

    def rg(g):
        return [[r(v, 2) for v in row] for row in g]

    return {
        "years": years,
        "monthly": monthly,
        "frost": frost,
        "annual": {k: [r(v, 2) for v in vals] for k, vals in annual_series.items()},
        "trends": trends,
        "by_year": {
            "precip": rg(g_precip), "precip_imerg": rg(g_imerg), "tmax": rg(g_tmax), "tmin": rg(g_tmin),
            "wet_root": rg(g_wet), "wet_root_z": z_grid, "erosivity": rg(g_ei),
            "heat_days_35": rg(g_heat35), "frost_days": rg(g_frost), "wet_days": rg(g_wetdays),
        },
        "drought_months_per_year": drought_months,
        "annual_precip_mm": r(sum(monthly["precip"]), 0),
        "annual_et0_mm": r(sum(monthly["et0"]), 0),
        "mean_annual_temp_c": r(mean(monthly["tmean"]), 1),
        "aridity_index": r(sum(monthly["precip"]) / max(1.0, sum(monthly["et0"])), 2),
    }


def _frost_dates(dates: list[str], tmin: list[float | None], years: list[int], lat: float) -> dict:
    """Last spring and first autumn frost (Tmin < 0 C) by year, as day-of-year."""
    by_year: dict[int, list[tuple[int, float]]] = defaultdict(list)
    from datetime import date

    for d, v in zip(dates, tmin):
        if v is None:
            continue
        y = int(d[:4])
        doy = date(y, int(d[4:6]), int(d[6:8])).timetuple().tm_yday
        if lat < 0:  # shift so "mid-season" is day 183 in both hemispheres
            doy = (doy + 182) % 365 + 1
        by_year[y].append((doy, v))
    last_spring, first_fall, free = [], [], []
    for y in years:
        days = by_year.get(y, [])
        spring = [doy for doy, v in days if v < 0 and doy < 196]
        fall = [doy for doy, v in days if v < 0 and doy >= 196]
        ls = max(spring) if spring else 0
        ff = min(fall) if fall else 366
        last_spring.append(ls)
        first_fall.append(ff)
        free.append(ff - ls)
    return {
        "last_spring_frost_doy_median": r(percentile(last_spring, 50), 0),
        "last_spring_frost_doy_p90": r(percentile(last_spring, 90), 0),
        "first_fall_frost_doy_median": r(percentile(first_fall, 50), 0),
        "first_fall_frost_doy_p10": r(percentile(first_fall, 10), 0),
        "frost_free_days_median": r(percentile(free, 50), 0),
        "frost_free_days_p10": r(percentile(free, 10), 0),
        "hemisphere_shifted": lat < 0,
    }


def monthly_climatology(series: dict, how: str = "mean") -> dict:
    """Composite series (16-day NDVI, 8-day LST/ET) -> monthly normals and a year-by-month grid.

    how="mean" averages composites in the month; how="rate8" treats values as 8-day totals
    (MOD16 ET) and converts them to a monthly total.
    """
    buckets: dict[tuple[int, int], list[float]] = defaultdict(list)
    for d, v in zip(series.get("dates", []), series.get("values", [])):
        if v is not None:
            buckets[(int(d[:4]), int(d[5:7]) - 1)].append(v)
    years = sorted({y for y, _ in buckets})
    grid = []
    for y in years:
        row = []
        for m in range(12):
            vals = buckets.get((y, m))
            if not vals:
                row.append(None)
            elif how == "rate8":
                row.append(r(sum(vals) / len(vals) / 8.0 * DAYS_IN_MONTH[m], 1))
            else:
                row.append(r(sum(vals) / len(vals), 3))
        grid.append(row)
    normals = [r(mean([row[m] for row in grid], default=float("nan")), 3) for m in range(12)]
    normals = [None if v is None or math.isnan(v) else v for v in normals]
    n_obs = sum(len(v) for v in buckets.values())
    return {"years": years, "monthly": normals, "by_year": grid, "n_observations": n_obs,
            "provenance": series.get("provenance")}


def compare_precip_sources(power: dict, daymet: dict | None) -> dict:
    """Satellite/reanalysis rain vs the ground-gauge reference, month by month."""
    pm = _month_buckets(power["dates"], power["series"]["precip"])
    im = _month_buckets(power["dates"], power["series"]["precip_imerg"])
    gm = _month_buckets(daymet["dates"], daymet["series"]["precip"]) if daymet else {}
    keys = sorted(set(pm) & set(gm)) if gm else sorted(pm)

    def total(bk, k):
        vals = bk.get(k)
        return sum(vals) * DAYS_IN_MONTH[k[1]] / len(vals) if vals else None

    rows = [(k, total(pm, k), total(im, k), total(gm, k) if gm else None) for k in keys]

    def stats(idx: int) -> dict | None:
        pairs = [(row[idx], row[3]) for row in rows if row[idx] is not None and row[3] is not None]
        if len(pairs) < 12:
            return None
        sat, ground = [p[0] for p in pairs], [p[1] for p in pairs]
        bias = (sum(sat) - sum(ground)) / max(1.0, sum(ground)) * 100
        rmse = math.sqrt(sum((a - c) ** 2 for a, c in pairs) / len(pairs))
        return {"correlation": r(pearson(sat, ground), 2), "bias_pct": r(bias, 1), "rmse_mm_month": r(rmse, 1), "n_months": len(pairs)}

    def normals(idx: int) -> list[float | None]:
        out = []
        for m in range(12):
            vals = [row[idx] for row in rows if row[0][1] == m and row[idx] is not None]
            out.append(r(sum(vals) / len(vals), 1) if vals else None)
        return out

    def heavy_days(daily: dict | None, key: str) -> float | None:
        if not daily:
            return None
        vals = [v for v in daily["series"][key] if v is not None]
        n_years = max(1, len({d[:4] for d in daily["dates"]}))
        return r(sum(1 for v in vals if v >= 25.0) / n_years, 1)

    recent = sorted({k[0] for k in keys})[-3:]
    return {
        "monthly_normals": {"merra2": normals(1), "imerg": normals(2), "ground": normals(3) if gm else None},
        "vs_ground": {"merra2": stats(1), "imerg": stats(2)} if gm else None,
        "heavy_rain_days_per_year": {
            "merra2": heavy_days(power, "precip"), "imerg": heavy_days(power, "precip_imerg"),
            "ground": heavy_days(daymet, "precip"),
        },
        "recent_months": [
            {"year": k[0], "month": k[1], "merra2": r(a, 1), "imerg": r(c, 1), "ground": r(g, 1)}
            for k, a, c, g in rows if k[0] in recent
        ],
        "ground_provenance": daymet.get("provenance") if daymet else None,
    }
