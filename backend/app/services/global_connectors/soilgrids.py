"""ISRIC SoilGrids 2.0 via its keyless REST API (global, 250 m).

Malaysia has no public field-scale soil survey API, so the profile under a field comes
from SoilGrids' machine-learned soil property maps. One request returns texture, organic
carbon, bulk density, pH, CEC and the water retained at field capacity and wilting point
for five depth intervals. Missing hydrology (Ksat, erodibility, runoff group) is derived
with published pedotransfer functions, and every derived number is labelled as such.

SoilGrids masks some pixels (towns, water, some peat and highland forest). When the field
pixel is empty the connector steps outward in a small ring and says how far it went.

API: https://rest.isric.org/soilgrids/v2.0/docs  (fair use: about 5 requests a minute)
"""
from __future__ import annotations

import math

from app.services.nasa_connectors import base
from app.utils.geo import haversine_km, offset_latlon, usda_texture_class

PROPERTIES_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
CLASSIFICATION_URL = "https://rest.isric.org/soilgrids/v2.0/classification/query"
PROPS = ["sand", "silt", "clay", "soc", "bdod", "phh2o", "cec", "wv0033", "wv1500", "cfvo"]
DEPTHS = [("0-5cm", 0, 5), ("5-15cm", 5, 15), ("15-30cm", 15, 30), ("30-60cm", 30, 60), ("60-100cm", 60, 100)]
TOPSOIL_CM = 30.0
# rings searched when the field pixel itself is masked (metres)
SEARCH_RINGS_M = [0.0, 300.0, 800.0, 1600.0]


def _query(lat: float, lon: float) -> tuple[dict | None, str]:
    params = [("lon", round(lon, 5)), ("lat", round(lat, 5))]
    params += [("property", p) for p in PROPS] + [("depth", d) for d, _a, _b in DEPTHS] + [("value", "mean")]
    payload, access = base.fetch("soilgrids", PROPERTIES_URL, params=params, timeout_s=60, retries=1)
    layers = {}
    for layer in (payload.get("properties") or {}).get("layers", []):
        factor = float((layer.get("unit_measure") or {}).get("d_factor") or 1.0)
        values = {}
        for d in layer.get("depths", []):
            v = (d.get("values") or {}).get("mean")
            values[d["label"]] = None if v is None else float(v) / factor
        layers[layer["name"]] = values
    if not layers or all(v is None for v in layers.get("clay", {}).values()):
        return None, access
    return layers, access


def _wrb(lat: float, lon: float) -> dict | None:
    try:
        payload, _ = base.fetch("soilgrids-wrb", CLASSIFICATION_URL,
                                params={"lon": round(lon, 5), "lat": round(lat, 5), "number_classes": 3},
                                timeout_s=45, retries=0)
    except base.ConnectorError:
        return None
    if not payload.get("wrb_class_name"):
        return None
    return {"name": payload["wrb_class_name"], "probabilities": payload.get("wrb_class_probability") or []}


def fetch_soil_profile(lat: float, lon: float) -> dict:
    found = None
    for ring in SEARCH_RINGS_M:
        bearings = [(0, 0)] if ring == 0 else [(1, 0), (0, 1), (-1, 0), (0, -1), (0.7, 0.7), (-0.7, -0.7), (0.7, -0.7), (-0.7, 0.7)]
        for north, east in bearings:
            la, lo = offset_latlon(lat, lon, north * ring, east * ring) if ring else (lat, lon)
            layers, access = _query(la, lo)
            if layers:
                found = (la, lo, layers, access)
                break
        if found:
            break
    if not found:
        raise base.ConnectorError("SoilGrids has no soil estimate within 1.6 km of this coordinate (water, town or masked pixel)")
    la, lo, layers, access = found
    moved_m = haversine_km(lat, lon, la, lo) * 1000.0
    profile = harmonise(layers)
    wrb = _wrb(la, lo)
    profile["taxonomic_order"] = wrb["name"] if wrb else None
    profile["wrb_probabilities"] = wrb["probabilities"] if wrb else []
    profile["series"] = f"{wrb['name'] if wrb else 'Unclassified soil'} ({profile['texture_class']}, SoilGrids 250 m)"
    profile["map_unit_name"] = profile["series"]
    profile["sample_offset_m"] = round(moved_m, 0)
    note = ("Machine-learned 250 m estimate, not a surveyed map unit: expect errors of 10-15 % clay and wide "
            "organic-carbon ranges, especially on peat and in the highlands. Ksat, erodibility and runoff group "
            "are derived with pedotransfer functions.")
    if moved_m > 1:
        note += f" The field pixel was masked, so the nearest valid pixel {moved_m:.0f} m away was used."
    profile["provenance"] = base.provenance(
        "ISRIC SoilGrids 2.0", "Soil properties 0-100 cm (texture, SOC, bulk density, pH, CEC, water retention)", access,
        resolution_m=250, cadence="static model (2020)", url="https://soilgrids.org/", note=note,
    )
    return profile


def _weighted(values: dict, top: float, bottom: float, default: float | None = None) -> float | None:
    acc = wsum = 0.0
    for label, d0, d1 in DEPTHS:
        v = values.get(label)
        thick = max(0.0, min(d1, bottom) - max(d0, top))
        if v is None or thick <= 0:
            continue
        acc += v * thick
        wsum += thick
    return acc / wsum if wsum else default


def williams_k(sand: float, silt: float, clay: float, oc_pct: float) -> float:
    """USLE soil erodibility (US customary units, as SSURGO Kw) from the EPIC equations
    (Williams 1995). Tends to over-predict K on well-aggregated tropical Oxisols."""
    sn1 = 1.0 - sand / 100.0
    f_csand = 0.2 + 0.3 * math.exp(-0.256 * sand * (1.0 - silt / 100.0))
    f_clsi = (silt / max(1.0, clay + silt)) ** 0.3
    f_orgc = 1.0 - 0.25 * oc_pct / (oc_pct + math.exp(3.72 - 2.95 * oc_pct))
    f_hisand = 1.0 - 0.7 * sn1 / (sn1 + math.exp(-5.51 + 22.9 * sn1))
    return round(max(0.05, min(0.55, f_csand * f_clsi * f_orgc * f_hisand)), 3)


def saxton_ksat_um_s(sand: float, clay: float, om_pct: float, bd: float | None = None) -> float:
    """Saturated conductivity from Saxton & Rawls (2006), in micrometres per second."""
    s, c, om = sand / 100.0, clay / 100.0, min(om_pct, 8.0)
    t1500 = -0.024 * s + 0.487 * c + 0.006 * om + 0.005 * s * om - 0.013 * c * om + 0.068 * s * c + 0.031
    wp = t1500 + (0.14 * t1500 - 0.02)
    t33 = -0.251 * s + 0.195 * c + 0.011 * om + 0.006 * s * om - 0.027 * c * om + 0.452 * s * c + 0.299
    fc = t33 + (1.283 * t33**2 - 0.374 * t33 - 0.015)
    ts33 = 0.278 * s + 0.034 * c + 0.022 * om - 0.018 * s * om - 0.027 * c * om - 0.584 * s * c + 0.078
    s33 = ts33 + (0.636 * ts33 - 0.107)
    sat = fc + s33 - 0.097 * s + 0.043
    b = (math.log(1500) - math.log(33)) / max(1e-3, math.log(max(fc, 0.05)) - math.log(max(wp, 0.01)))
    lam = 1.0 / b
    ksat_mm_h = 1930.0 * max(0.0, sat - fc) ** (3.0 - lam)
    return round(ksat_mm_h / 3.6, 2)


def hydrologic_group(ksat_um_s: float) -> str:
    """NRCS runoff group from saturated conductivity of the least-transmissive surface layer."""
    if ksat_um_s >= 40.0:
        return "A"
    if ksat_um_s >= 10.0:
        return "B"
    if ksat_um_s >= 1.0:
        return "C"
    return "D"


DRAINAGE = {"A": "Well drained", "B": "Well drained", "C": "Moderately well drained", "D": "Somewhat poorly drained"}


def harmonise(layers: dict) -> dict:
    """Depth-weight SoilGrids layers to the 0-30 cm topsoil the engines use."""
    def top(name: str, default: float) -> float:
        v = _weighted(layers.get(name, {}), 0.0, TOPSOIL_CM)
        return default if v is None else v

    sand, silt, clay = top("sand", 35.0), top("silt", 35.0), top("clay", 30.0)
    total = sand + silt + clay
    if total > 0:
        sand, silt, clay = (100.0 * x / total for x in (sand, silt, clay))
    soc_g_kg = top("soc", 15.0)
    om = soc_g_kg / 10.0 * 1.724
    bd = top("bdod", 1.3)
    fc = layers.get("wv0033", {})
    wp = layers.get("wv1500", {})
    awc_by_depth = {}
    for label, _a, _b in DEPTHS:
        if fc.get(label) is not None and wp.get(label) is not None:
            awc_by_depth[label] = max(0.02, (fc[label] - wp[label]) / 100.0)
    awc_top = _weighted(awc_by_depth, 0.0, TOPSOIL_CM, 0.14)
    awc_profile = sum(awc_by_depth.get(label, awc_top) * (d1 - d0) * 10.0 for label, d0, d1 in DEPTHS)
    awc_profile += awc_by_depth.get("60-100cm", awc_top) * 50.0 * 10.0  # 100-150 cm assumed like 60-100 cm
    gravel = top("cfvo", 0.0)
    ksat = saxton_ksat_um_s(sand, clay, om, bd)
    hsg = hydrologic_group(ksat)
    return {
        "mukey": None,
        "component_pct": None,
        "texture_class": usda_texture_class(sand, silt, clay),
        "sand_pct": round(sand, 1), "silt_pct": round(silt, 1), "clay_pct": round(clay, 1),
        "organic_matter_pct": round(om, 2),
        "bulk_density_g_cm3": round(bd, 2),
        "awc_cm_cm": round(awc_top * (1.0 - gravel / 100.0), 3),
        "awc_profile_mm": round(awc_profile * (1.0 - gravel / 100.0), 0),
        "ksat_um_s": ksat,
        "ph": round(top("phh2o", 5.5), 1),
        "ec_ds_m": 0.0,
        "cec_meq_100g": round(top("cec", 10.0), 1),
        "coarse_fragments_pct": round(gravel, 1),
        "kw_factor": williams_k(sand, silt, clay, soc_g_kg / 10.0),
        "t_factor_tons_ac_yr": 5.0,
        "hydrologic_group": hsg,
        "hydrologic_group_raw": f"{hsg} (from Saxton-Rawls Ksat)",
        "drainage_class": DRAINAGE[hsg],
        "representative_slope_pct": None,
        "capability_class_nonirrigated": None,
        "root_zone_depth_cm": 150.0,
        "restrictive_layer": None,
        "derived": ["ksat_um_s", "kw_factor", "hydrologic_group", "drainage_class", "t_factor_tons_ac_yr"],
    }
