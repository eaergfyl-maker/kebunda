"""Spatial harmonisation and confidence scoring.

The sensors feeding FieldShift see the world at wildly different scales: GRACE weighs
water over ~300 km, MERRA-2 cells are ~55 km, GAEZ ~9 km, SMAP 9 km, IMERG 10 km, MODIS
250-1000 m, SoilGrids 250 m, SRTM 30 m, Sentinel-2 10 m, and a Malaysian smallholding is a
few hundred metres across. This module

  1. fuses redundant estimates of the same variable (three rainfall products) by
     inverse-variance weighting, with the error of each product measured against the
     ground reference rather than assumed;
  2. rescales coarse soil wetness to the field using the field's own SoilGrids texture
     (Saxton & Rawls pedotransfer functions);
  3. scores every layer for how well a pixel that size can represent this field
     ("resolution gap"), and rolls the scores up into a confidence per decision dimension.

Nothing here invents sub-pixel detail. Where a coarse pixel cannot resolve the field, the
honest output is a wider uncertainty band, and that is what gets reported.
"""
from __future__ import annotations

import math

from app.utils.stats import clamp, mean

# Distance over which each variable typically stays similar (km). A pixel much larger than
# this cannot represent one field. Values are order-of-magnitude decorrelation lengths.
SPATIAL_SCALE_KM = {
    "temperature": 150.0, "precip": 40.0, "soil_moisture": 15.0, "groundwater": 100.0,
    "vegetation": None, "surface_temp": None, "et": None,  # None -> use the field's own width
    "soil": 0.10, "terrain": 0.05, "crop_history": None, "suitability": 30.0,
}
ACCESS_WEIGHT = {"live": 1.0, "cache": 1.0, "curated": 0.8, "proxy": 0.7, "unavailable": 0.0}
DEFAULT_REL_ERROR = {"merra2": 0.25, "imerg": 0.22, "ground": 0.10}
GAUGE_ERROR_PER_KM = 0.004  # a gauge 50 km away carries ~0.2 extra relative error for the field


def saxton_rawls(sand_pct: float, clay_pct: float, om_pct: float) -> dict:
    """Soil water characteristics from texture and organic matter (Saxton & Rawls 2006)."""
    s, c, om = sand_pct / 100.0, clay_pct / 100.0, min(om_pct, 8.0)
    t1500 = -0.024 * s + 0.487 * c + 0.006 * om + 0.005 * s * om - 0.013 * c * om + 0.068 * s * c + 0.031
    wp = t1500 + (0.14 * t1500 - 0.02)
    t33 = -0.251 * s + 0.195 * c + 0.011 * om + 0.006 * s * om - 0.027 * c * om + 0.452 * s * c + 0.299
    fc = t33 + (1.283 * t33**2 - 0.374 * t33 - 0.015)
    ts33 = 0.278 * s + 0.034 * c + 0.022 * om - 0.018 * s * om - 0.027 * c * om - 0.584 * s * c + 0.078
    s33 = ts33 + (0.636 * ts33 - 0.107)
    sat = fc + s33 - 0.097 * s + 0.043
    return {"wilting_point": round(wp, 3), "field_capacity": round(fc, 3), "saturation": round(sat, 3),
            "available_water": round(fc - wp, 3)}


def fuse_precip(comparison: dict) -> dict:
    """Inverse-variance fusion of MERRA-2, GPM IMERG and the ground-gauge reference.

    Each satellite/reanalysis product's error is its monthly RMSE against the ground
    reference at this site, so a product that tracks the gauges gets more say. The spread
    between sources is kept as part of the uncertainty.
    """
    normals = comparison["monthly_normals"]
    sources = {k: v for k, v in normals.items() if v and any(x is not None for x in v)}
    vs = comparison.get("vs_ground") or {}
    ground = sources.get("ground")
    ground_mean = mean(ground, 0.0) if ground else 0.0
    gauge_km = float((comparison.get("ground_station") or {}).get("distance_km") or 0.0)
    rel_err = {}
    for name in sources:
        stat = vs.get(name) if name != "ground" else None
        if stat and ground_mean > 0:
            # part of the mismatch against a distant gauge is the distance itself, not satellite error
            rel_err[name] = clamp(stat["rmse_mm_month"] / ground_mean - 0.5 * GAUGE_ERROR_PER_KM * gauge_km, 0.08, 0.9)
        else:
            rel_err[name] = DEFAULT_REL_ERROR[name]
    if "ground" in rel_err:
        rel_err["ground"] = clamp(DEFAULT_REL_ERROR["ground"] + GAUGE_ERROR_PER_KM * gauge_km, 0.08, 0.9)
    weights = {k: 1.0 / rel_err[k] ** 2 for k in sources}
    wsum = sum(weights.values()) or 1.0
    fused, sigma = [], []
    for m in range(12):
        vals = {k: v[m] for k, v in sources.items() if v[m] is not None}
        if not vals:
            fused.append(0.0)
            sigma.append(0.5)
            continue
        w = {k: weights[k] for k in vals}
        ws = sum(w.values())
        est = sum(vals[k] * w[k] for k in vals) / ws
        formal = math.sqrt(1.0 / ws)
        spread = (max(vals.values()) - min(vals.values())) / (2.0 * est) if est > 1.0 and len(vals) > 1 else 0.0
        fused.append(round(est, 1))
        sigma.append(round(clamp(math.sqrt(formal**2 + (0.5 * spread) ** 2), 0.05, 0.8), 3))
    merra = sources.get("merra2") or fused
    bias = [round(clamp(f / m, 0.5, 1.6), 3) if m and m > 2.0 else 1.0 for f, m in zip(fused, merra)]
    return {
        "monthly_mm": fused,
        "relative_sigma": sigma,
        "annual_mm": round(sum(fused), 0),
        "annual_by_source": {k: round(sum(x for x in v if x is not None), 0) for k, v in sources.items()},
        "weights": {k: round(weights[k] / wsum, 2) for k in sources},
        "measured_error": {k: round(v, 2) for k, v in rel_err.items()},
        "bias_vs_merra2": bias,
        "method": ("Inverse-variance weighted mean of MERRA-2 (55 km), GPM IMERG (10 km) and the nearest MetMalaysia rain gauge "
                   "(GHCN-Daily). Weights come from each product's monthly error against the gauge; the gauge's own weight "
                   "shrinks with its distance from the field."),
        "gauge_distance_km": gauge_km or None,
        "has_ground": bool(ground),
    }


def downscale_soil_moisture(wet_root: list[float], soil: dict, root_zone_cm: float) -> dict:
    """Coarse relative wetness -> field-scale plant-available water using the field's texture.

    A 55 km model cell reports saturation for an average soil. Two fields in the same cell
    with different textures hold very different amounts of *plant-available* water at the
    same saturation, so the conversion uses this field's SoilGrids sand, clay and organic matter.
    """
    h = saxton_rawls(soil.get("sand_pct", 40.0), soil.get("clay_pct", 20.0), soil.get("organic_matter_pct", 2.0))
    out_frac, out_mm, theta = [], [], []
    for w in wet_root:
        vol = clamp(w, 0.0, 1.0) * h["saturation"]
        paw = clamp((vol - h["wilting_point"]) / max(0.01, h["available_water"]))
        theta.append(round(vol, 3))
        out_frac.append(round(paw, 3))
        out_mm.append(round(paw * h["available_water"] * root_zone_cm * 10.0, 0))
    return {"volumetric": theta, "plant_available_fraction": out_frac, "plant_available_mm": out_mm, "hydraulics": h,
            "method": "MERRA-2 / SMAP-class relative wetness x Saxton-Rawls saturation for this field's SoilGrids texture."}


def _layer(layer_id: str, variable: str, label: str, prov: dict | None, field_km: float, *, method: str,
           completeness: float = 1.0, used_for: str = "") -> dict:
    prov = prov or {"access": "unavailable", "source": label, "dataset": label}
    res_km = (prov.get("resolution_m") or 0) / 1000.0
    scale = SPATIAL_SCALE_KM.get(variable) or field_km
    representativeness = 1.0 / (1.0 + res_km / scale) if res_km > 0 else 0.9
    confidence = ACCESS_WEIGHT.get(prov.get("access", "unavailable"), 0.0) * representativeness * clamp(completeness, 0.2, 1.0)
    pixels = (field_km / res_km) ** 2 if res_km > 0 else None
    return {
        "id": layer_id, "variable": variable, "label": label,
        "source": prov.get("source"), "dataset": prov.get("dataset"), "access": prov.get("access"),
        "native_resolution_m": prov.get("resolution_m"), "cadence": prov.get("cadence"), "period": prov.get("period"),
        "url": prov.get("url"), "note": prov.get("note"),
        "pixel_to_field_ratio": round(res_km / field_km, 2) if res_km else None,
        "pixels_inside_field": round(pixels, 2) if pixels is not None else None,
        "representativeness": round(representativeness, 2),
        "completeness": round(completeness, 2),
        "confidence": round(confidence, 2),
        "harmonisation": method, "used_for": used_for,
    }


def layer_inventory(obs: dict, soil: dict | None, area_ha: float) -> list[dict]:
    """One row per data layer: where it came from, how coarse it is next to this field, and
    how much weight the tool gives it."""
    field_km = math.sqrt(max(1.0, area_ha) * 0.01)
    clim_prov = obs["climate"].get("provenance")
    imerg_prov = {**(clim_prov or {}), "resolution_m": 10_000, "source": "NASA GPM IMERG (via POWER)",
                  "dataset": "IMERG daily precipitation"} if clim_prov else None
    sm_prov = (obs.get("soil_moisture") or {}).get("provenance")
    ground_prov = (obs.get("precip_comparison") or {}).get("ground_provenance")
    ndvi, lst, et = obs.get("ndvi") or {}, obs.get("lst") or {}, obs.get("et") or {}

    def complete(block: dict, per_year: float) -> float:
        yrs = len(block.get("years") or [])
        return clamp(block.get("n_observations", 0) / (per_year * yrs)) if yrs else 0.0

    cycles = obs.get("crop_cycles") or {}
    suit = obs.get("gaez") or {}
    from_s2 = "Sentinel" in str((ndvi.get("provenance") or {}).get("source"))
    ndvi_label = "Vegetation greenness (Sentinel-2 NDVI, 10 m)" if from_s2 else "Vegetation greenness (MODIS NDVI)"
    ndvi_per_year = 40 if from_s2 else 23
    rows = [
        _layer("power_temp", "temperature", "Air temperature, humidity, sunshine", clim_prov, field_km,
               method="Daily values aggregated to calendar months; extremes counted from the daily record first.",
               used_for="Growing degree days, frost and heat days, reference ET"),
        _layer("power_precip", "precip", "Rainfall (MERRA-2, bias-corrected)", clim_prov, field_km,
               method="Fused with IMERG and gauges by inverse-variance weighting.", used_for="Water balance, runoff"),
        _layer("imerg", "precip", "Rainfall from orbit (GPM IMERG)", imerg_prov, field_km,
               method="Daily totals aggregated to months; storm days counted before aggregation.",
               used_for="Storm size, erosive rain days"),
        _layer("ground_precip", "precip", "Rain gauge (MetMalaysia via NOAA GHCN-Daily)", ground_prov, field_km,
               method="Months with under 70% of days reported are dropped; used as the reference that sets the weight of each satellite product.",
               used_for="Ground truth for rainfall"),
        _layer("soil_moisture", "soil_moisture", "Root-zone soil moisture (SMAP-class)", sm_prov, field_km,
               method="Relative wetness rescaled with this field's SoilGrids texture (Saxton-Rawls).",
               used_for="Drought months, planting moisture"),
        _layer("ndvi", "vegetation", ndvi_label, ndvi.get("provenance"), field_km,
               method="Clear looks (cloud, shadow and cirrus masked) averaged to months.",
               completeness=complete(ndvi, ndvi_per_year), used_for="Bare-field months, crop cycles per year, checking the assumed crop calendar"),
        _layer("lst", "surface_temp", "Land-surface temperature (MODIS, ECOSTRESS stand-in)", lst.get("provenance"), field_km,
               method="8-day daytime composites averaged to months.", completeness=complete(lst, 46),
               used_for="Heat-stress months"),
        _layer("et", "et", "Evapotranspiration (MODIS MOD16)", et.get("provenance"), field_km,
               method="8-day totals converted to monthly totals.", completeness=complete(et, 46),
               used_for="Cross-check on modelled crop water use"),
        _layer("grace", "groundwater", "Water storage trend (GRACE / GRACE-FO)", (obs.get("grace") or {}).get("provenance"), field_km,
               method="Regional trend used as context only; never downscaled to the field.",
               used_for="Is the regional aquifer being drawn down?"),
        _layer("srtm", "terrain", "Elevation and slope (SRTM)", (obs.get("terrain") or {}).get("provenance"), field_km,
               method="3x3 window Horn slope; noise-level relief on flat paddy is ignored.", used_for="Runoff and erosion (LS factor)"),
        _layer("soil", "soil", "Soil properties (ISRIC SoilGrids 250 m)", (soil or {}).get("provenance"), field_km,
               method="Depth-weighted over 0-30 cm; Ksat, erodibility and runoff group from pedotransfer functions.",
               used_for="Water-holding capacity, erodibility, organic matter, runoff class"),
        _layer("gaez", "suitability", "Crop suitability (FAO GAEZ v4)", suit.get("provenance"), field_km,
               method="Grid-cell suitability index read per crop; a cross-check on the field-scale screen.",
               completeness=clamp(len([1 for v in (suit.get("crops") or {}).values() if v.get("si") is not None]) / 8.0),
               used_for="Second opinion on which crops suit the area, today and in the 2050s"),
        _layer("crop_cycles", "crop_history", "Crop cycles (Sentinel-2 NDVI peaks)", cycles.get("provenance"), field_km,
               method="Green peaks counted on a smoothed 8-day NDVI series.", completeness=clamp(len(cycles.get("years") or []) / 4.0),
               used_for="Confirming how many crops a year the field carries"),
    ]
    return rows


def confidence_by_dimension(layers: list[dict], has_local_yields: bool, has_local_market: bool) -> dict:
    """Roll layer confidence up to the five decision dimensions.

    data = how good the inputs are for this field; model = how much a monthly planning model
    can be trusted for that question at all. The product is what the UI shows.
    """
    c = {row["id"]: row["confidence"] for row in layers}
    precip = max(c.get("ground_precip", 0), c.get("imerg", 0) * 0.9, c.get("power_precip", 0))
    data = {
        "water": mean([precip, c.get("power_temp", 0), c.get("soil", 0), max(c.get("soil_moisture", 0), 0.3)]),
        "soil": mean([c.get("soil", 0), c.get("power_temp", 0), precip]),
        "erosion": mean([c.get("imerg", 0), c.get("soil", 0), max(c.get("srtm", 0), 0.3), max(c.get("ndvi", 0), 0.3)]),
        "pest": mean([max(c.get("crop_cycles", 0), 0.35), 0.75]),
        "income": mean([0.8 if has_local_yields else 0.45, 0.8 if has_local_market else 0.4, precip]),
    }
    model = {"water": 0.80, "soil": 0.55, "erosion": 0.65, "pest": 0.65, "income": 0.55}
    out = {}
    for k in data:
        score = clamp(data[k] ** 0.5 * model[k] ** 0.5)
        out[k] = {"data": round(data[k], 2), "model": model[k], "combined": round(score, 2),
                  "label": "high" if score >= 0.72 else "moderate" if score >= 0.55 else "low"}
    out["overall"] = round(mean([v["combined"] for v in out.values()]), 2)
    return out
