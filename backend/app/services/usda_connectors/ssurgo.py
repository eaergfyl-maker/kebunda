"""USDA NRCS SSURGO via Soil Data Access (keyless SQL-over-REST).

Looks up the soil map unit under a coordinate and harmonises its dominant component into
the compact profile the engines use (0-30 cm weighted horizon properties).
Docs: https://sdmdataaccess.nrcs.usda.gov/
"""
from __future__ import annotations

from app.services.nasa_connectors import base
from app.utils.geo import usda_texture_class

SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"
TOPSOIL_CM = 30.0

_QUERY = """
SELECT mu.mukey, mu.muname, c.cokey, c.compname, c.comppct_r, c.hydgrp, c.drainagecl,
       c.slope_r, c.tfact, c.taxorder, c.nirrcapcl,
       h.hzdept_r, h.hzdepb_r, h.sandtotal_r, h.silttotal_r, h.claytotal_r, h.om_r,
       h.dbthirdbar_r, h.awc_r, h.ksat_r, h.ph1to1h2o_r, h.kwfact, h.ec_r, h.cec7_r
FROM mapunit mu
JOIN component c ON c.mukey = mu.mukey AND c.majcompflag = 'Yes'
LEFT JOIN chorizon h ON h.cokey = c.cokey
WHERE mu.mukey IN (SELECT mukey FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('point({lon} {lat})'))
ORDER BY c.comppct_r DESC, c.cokey, h.hzdept_r
"""

_RESTRICTION_QUERY = """
SELECT TOP 1 r.resdept_r, r.reskind FROM corestrictions r WHERE r.cokey = {cokey} ORDER BY r.resdept_r
"""


def _sql(query: str) -> list[dict]:
    payload, access = base.fetch(
        "ssurgo", SDA_URL, method="POST",
        json_body={"format": "JSON+COLUMNNAME", "query": " ".join(query.split())},
    )
    table = payload.get("Table") if isinstance(payload, dict) else None
    if not table or len(table) < 2:
        return []
    header, rows = table[0], table[1:]
    out = [dict(zip(header, row)) for row in rows]
    for row in out:
        row["_access"] = access
    return out


def _f(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def fetch_soil_profile(lat: float, lon: float) -> dict:
    rows = _sql(_QUERY.format(lat=round(lat, 6), lon=round(lon, 6)))
    if not rows:
        raise base.ConnectorError("SSURGO has no map unit at this coordinate (outside the U.S. survey area?)")
    cokey = rows[0]["cokey"]
    comp = [r for r in rows if r["cokey"] == cokey]
    profile = harmonise(comp)
    try:
        restr = _sql(_RESTRICTION_QUERY.format(cokey=int(cokey)))
        if restr and _f(restr[0].get("resdept_r")) is not None:
            profile["restrictive_layer"] = {"depth_cm": _f(restr[0]["resdept_r"]), "kind": restr[0].get("reskind")}
            profile["root_zone_depth_cm"] = min(profile["root_zone_depth_cm"], max(25.0, _f(restr[0]["resdept_r"])))
    except base.ConnectorError:
        pass
    profile["provenance"] = base.provenance(
        "USDA NRCS", "SSURGO via Soil Data Access (dominant component, 0-30 cm weighted)", rows[0]["_access"],
        resolution_m=30, cadence="static survey", url="https://websoilsurvey.nrcs.usda.gov/app/",
        note="Map units are drawn at 1:12,000-1:24,000. Inclusions of other soils inside the unit are normal.",
    )
    return profile


def harmonise(rows: list[dict]) -> dict:
    """Depth-weight the dominant component's horizons over the top 30 cm."""
    top = rows[0]
    acc: dict[str, float] = {}
    wsum: dict[str, float] = {}
    kw_surface = None
    profile_depth = 0.0
    awc_profile_mm = 0.0
    for h in rows:
        d0, d1 = _f(h.get("hzdept_r")), _f(h.get("hzdepb_r"))
        if d0 is None or d1 is None or d1 <= d0:
            continue
        profile_depth = max(profile_depth, d1)
        awc = _f(h.get("awc_r"))
        if awc is not None:
            awc_profile_mm += awc * (min(d1, 150.0) - min(d0, 150.0)) * 10.0
        if kw_surface is None and _f(h.get("kwfact")) is not None:
            kw_surface = _f(h.get("kwfact"))
        thick = max(0.0, min(d1, TOPSOIL_CM) - d0)
        if thick <= 0:
            continue
        for key in ("sandtotal_r", "silttotal_r", "claytotal_r", "om_r", "dbthirdbar_r", "awc_r",
                    "ksat_r", "ph1to1h2o_r", "ec_r", "cec7_r"):
            v = _f(h.get(key))
            if v is not None:
                acc[key] = acc.get(key, 0.0) + v * thick
                wsum[key] = wsum.get(key, 0.0) + thick

    def w(key: str, default: float) -> float:
        return acc[key] / wsum[key] if wsum.get(key) else default

    sand, silt, clay = w("sandtotal_r", 35.0), w("silttotal_r", 40.0), w("claytotal_r", 25.0)
    hsg = (top.get("hydgrp") or "B").split("/")[0]
    return {
        "mukey": str(top.get("mukey")),
        "map_unit_name": top.get("muname"),
        "series": top.get("compname"),
        "component_pct": _f(top.get("comppct_r")),
        "taxonomic_order": top.get("taxorder"),
        "texture_class": usda_texture_class(sand, silt, clay),
        "sand_pct": round(sand, 1), "silt_pct": round(silt, 1), "clay_pct": round(clay, 1),
        "organic_matter_pct": round(w("om_r", 2.0), 2),
        "bulk_density_g_cm3": round(w("dbthirdbar_r", 1.35), 2),
        "awc_cm_cm": round(w("awc_r", 0.17), 3),
        "awc_profile_mm": round(awc_profile_mm, 0) if awc_profile_mm else None,
        "ksat_um_s": round(w("ksat_r", 9.0), 2),
        "ph": round(w("ph1to1h2o_r", 6.8), 1),
        "ec_ds_m": round(w("ec_r", 0.0), 1),
        "cec_meq_100g": round(w("cec7_r", 18.0), 1),
        "kw_factor": kw_surface if kw_surface is not None else 0.32,
        "t_factor_tons_ac_yr": _f(top.get("tfact"), 5.0),
        "hydrologic_group": hsg,
        "hydrologic_group_raw": top.get("hydgrp"),
        "drainage_class": top.get("drainagecl") or "Well drained",
        "representative_slope_pct": _f(top.get("slope_r")),
        "capability_class_nonirrigated": top.get("nirrcapcl"),
        "root_zone_depth_cm": min(150.0, profile_depth) if profile_depth else 120.0,
        "restrictive_layer": None,
    }
