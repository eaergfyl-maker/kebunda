"""FAO GAEZ v4 crop suitability at a point, from FAO's public ArcGIS image service.

GAEZ (Global Agro-Ecological Zones) rates land for each crop from climate, soil and
terrain on a 0-10000 suitability index at about 9 km. FieldShift reads two numbers per
crop for the field's grid cell:

  * baseline   1981-2010 climate (CRU TS 3.2), high-input management, rainfed or irrigated
  * future     2041-2070 under RCP8.5, median of the five GAEZ climate models

The index is a regional, potential-yield based rating. FieldShift uses it as an
independent cross-check on its own field-scale screen, never as a replacement for it.

Service: https://gaez-services.fao.org/server/rest/services/res05/ImageServer
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from statistics import median

from app.services.nasa_connectors import base

GAEZ_URL = "https://gaez-services.fao.org/server/rest/services/res05/ImageServer"
BASELINE_PERIOD = "1981-2010"
FUTURE_PERIOD = "2041-2070"
FUTURE_RCP = "RCP8.5"
SI_CLASSES = [(8500, "Very high"), (7000, "High"), (5500, "Good"), (4000, "Medium"),
              (2500, "Moderate"), (1000, "Marginal"), (1, "Very marginal"), (0, "Not suitable")]


def si_class(si: float | None) -> str | None:
    if si is None:
        return None
    return next(lbl for thr, lbl in SI_CLASSES if si >= thr)


def _catalogue(crop: str, water: str) -> list[dict]:
    where = (f"variable LIKE 'Suitability index%range%all land%' AND input_level='High' "
             f"AND crop='{crop}' AND water_supply='{water}'")
    payload, _ = base.fetch("gaez-catalogue", f"{GAEZ_URL}/query", params={
        "f": "json", "where": where, "outFields": "objectid,year,model,rcp,water_supply", "returnGeometry": "false",
    }, ttl_hours=24 * 90, timeout_s=60)
    return [f["attributes"] for f in payload.get("features", [])]


def _identify(object_id: int, lat: float, lon: float) -> float | None:
    payload, _ = base.fetch("gaez-identify", f"{GAEZ_URL}/identify", params={
        "f": "json", "geometryType": "esriGeometryPoint", "returnGeometry": "false", "returnCatalogItems": "false",
        "geometry": json.dumps({"x": round(lon, 4), "y": round(lat, 4), "spatialReference": {"wkid": 4326}}),
        "mosaicRule": json.dumps({"mosaicMethod": "esriMosaicLockRaster", "lockRasterIds": [object_id]}),
    }, timeout_s=45, retries=1)
    try:
        v = float(payload.get("value"))
    except (TypeError, ValueError):
        return None
    return v if 0 <= v <= 10000 else None


def crop_suitability(lat: float, lon: float, crops: dict[str, dict], *, irrigated: bool = False,
                     with_future: bool = True) -> dict:
    """Return {"crops": {crop_id: {...}}, "provenance": {...}} for every crop that names a GAEZ crop."""
    wanted = {cid: c["gaez"] for cid, c in crops.items() if c.get("gaez")}
    out: dict[str, dict] = {}

    def one(item: tuple[str, dict]):
        cid, g = item
        water = "Gravity Irrigation" if irrigated and g.get("irrigated") else "Rainfed"
        try:
            cat = _catalogue(g["crop"], water)
            if not cat and water != "Rainfed":
                water = "Rainfed"
                cat = _catalogue(g["crop"], water)
            base_ids = [r["objectid"] for r in cat if r["year"] == BASELINE_PERIOD]
            if not base_ids:
                return cid, None
            si = _identify(base_ids[0], lat, lon)
            future = None
            if with_future:
                fut_ids = [r["objectid"] for r in cat if r["year"] == FUTURE_PERIOD and r["rcp"] == FUTURE_RCP]
                vals = [v for v in (_identify(i, lat, lon) for i in fut_ids) if v is not None]
                future = median(vals) if vals else None
        except base.ConnectorError:
            return cid, None
        return cid, {
            "gaez_crop": g["crop"], "water_supply": water,
            "si": si, "class": si_class(si),
            "si_2050s": future, "class_2050s": si_class(future),
            "change_2050s": None if si is None or future is None else round(future - si, 0),
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        for cid, row in pool.map(one, wanted.items()):
            if row:
                out[cid] = row
    ok = any(r.get("si") is not None for r in out.values())
    return {
        "crops": out,
        "provenance": base.provenance(
            "FAO GAEZ v4", f"Crop suitability index, high inputs ({BASELINE_PERIOD} and {FUTURE_PERIOD} {FUTURE_RCP})",
            base.ACCESS_LIVE if ok else base.ACCESS_UNAVAILABLE, resolution_m=9000, cadence="30-year climate periods",
            url="https://gaez.fao.org/",
            note=("A 9 km regional rating of potential yield under high inputs. It does not know this field's drainage, "
                  "slope or irrigation layout; treat it as a second opinion on the field-scale screen.")
            if ok else "FAO's GAEZ service did not answer; the field-scale screen is used alone.",
        ),
    }
