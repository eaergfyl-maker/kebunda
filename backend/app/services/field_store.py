"""Field store: benchmark farms shipped in data/, plus custom fields built live from a coordinate."""
from __future__ import annotations

import hashlib
import json
import threading
from functools import lru_cache

from app.config import settings
from app.services.fusion_engine import observe
from app.services.rotation_engine.context import crops_by_id
from app.utils import cache

FARM_DIR = settings.data_dir / "benchmark-farms"
SOIL_DIR = settings.data_dir / "soil-profiles"
_custom: dict[str, dict] = {}
_lock = threading.Lock()

DEFAULT_EQUIPMENT = ["row_planter", "grain_drill", "combine", "corn_header", "flex_header"]


class FieldNotFound(KeyError):
    pass


@lru_cache(maxsize=1)
def benchmark_ids() -> list[str]:
    return sorted(p.stem for p in FARM_DIR.glob("*.json"))


@lru_cache(maxsize=16)
def _load_benchmark(field_id: str) -> dict:
    farm = json.loads((FARM_DIR / f"{field_id}.json").read_text(encoding="utf-8"))
    obs_path = FARM_DIR / "observations" / f"{field_id}.json"
    if not obs_path.exists():
        raise FieldNotFound(f"observations for {field_id} are missing; run `python -m scripts.build_benchmark_data {field_id}`")
    obs = json.loads(obs_path.read_text(encoding="utf-8"))
    soil_path = SOIL_DIR / f"{field_id}.json"
    soil = json.loads(soil_path.read_text(encoding="utf-8")) if soil_path.exists() else None
    return {"id": field_id, "kind": "benchmark", "farm": farm, "obs": obs, "soil": soil}


def get_field(field_id: str) -> dict:
    if field_id in benchmark_ids():
        return _load_benchmark(field_id)
    with _lock:
        if field_id in _custom:
            return _custom[field_id]
    stored = cache.get_stale("custom-field", field_id)
    if stored:
        with _lock:
            _custom[field_id] = stored
        return stored
    raise FieldNotFound(field_id)


def list_benchmarks() -> list[dict]:
    out = []
    for fid in benchmark_ids():
        try:
            f = _load_benchmark(fid)
        except FieldNotFound:
            continue
        farm, obs, soil = f["farm"], f["obs"], f["soil"] or {}
        c = obs["climate"]
        out.append({
            "id": fid, "kind": "benchmark", "name": farm["name"], "short_name": farm["short_name"], "region": farm["region"],
            "state": farm["state"], "county": farm["county"], "lat": farm["lat"], "lon": farm["lon"], "area_ha": farm["area_ha"],
            "headline": farm["headline"], "challenge_tags": farm["challenge_tags"],
            "baseline_name": farm["baseline_rotation"]["name"],
            "irrigation": farm["management"]["irrigation"]["label"],
            "annual_precip_mm": c["annual_precip_mm"], "mean_annual_temp_c": c["mean_annual_temp_c"],
            "soil_series": soil.get("series"), "soil_texture": soil.get("texture_class"),
            "organic_matter_pct": soil.get("organic_matter_pct"),
        })
    return out


def _baseline_from_cdl(cdl: dict | None) -> dict | None:
    """Read the rotation off the Cropland Data Layer history, if it resolves to crops we model."""
    crops = crops_by_id()
    if not cdl or len(cdl.get("years", [])) < 3:
        return None
    seq: list[list[str]] = []
    for y in cdl["years"]:
        if y.get("double_crop"):
            seq.append([c for c in y["double_crop"] if c in crops])
        elif y.get("crop_id") == "fallow":
            seq.append([])
        elif y.get("crop_id") in crops:
            seq.append([y["crop_id"]])
        else:
            return None  # pasture, orchard, developed land...: not an annual-crop rotation
    for length in (1, 2, 3):
        cycle = seq[-length:]
        if all(seq[i] == cycle[(i - (len(seq) - length)) % length] for i in range(len(seq))):
            break
    else:
        cycle = seq[-3:]
    if not any(cycle):
        return None
    span = f"{cdl['years'][0]['year']}-{cdl['years'][-1]['year']}"
    return {"name": "Rotation seen by the Cropland Data Layer", "years": cycle, "tillage": "conventional",
            "note": f"Read from USDA CDL {span}. Tillage is assumed conventional. Edit both to match your records."}


def create_custom_field(lat: float, lon: float, name: str | None = None, area_ha: float = 40.0,
                        irrigated: bool = False, allocation_mm: float = 400.0) -> dict:
    """Pull live NASA/USDA layers for a coordinate and assemble a field the engines can run on."""
    field_id = "custom-" + hashlib.sha1(f"{lat:.4f},{lon:.4f},{irrigated},{allocation_mm:.0f},{area_ha:.1f}".encode()).hexdigest()[:10]
    try:
        existing = get_field(field_id)
        if existing["soil"] is not None:  # a field built without its soil survey is rebuilt on the next request
            if name and existing["farm"]["name"] != name:
                existing["farm"]["name"] = existing["farm"]["short_name"] = name
            return existing
    except FieldNotFound:
        pass
    obs = observe.collect(lat, lon, depth="fast")  # raises ConnectorError if NASA POWER is unreachable
    soil = obs.pop("soil")
    c = obs["climate"]
    baseline = _baseline_from_cdl(obs["cdl"])
    assumed = baseline is None
    if assumed:
        humid = c["aridity_index"] >= 0.7 or irrigated
        baseline = {
            "name": "Assumed baseline: corn - soybean" if humid else "Assumed baseline: winter wheat - fallow",
            "years": [["corn"], ["soybean"]] if humid else [["winter_wheat"], []], "tillage": "conventional",
            "note": "No crop history could be read for this point, so a regional default was assumed. Replace it with your real rotation.",
        }
    label = name or f"Field at {abs(lat):.3f}°{'N' if lat >= 0 else 'S'}, {abs(lon):.3f}°{'E' if lon >= 0 else 'W'}"
    farm = {
        "id": field_id, "name": label, "short_name": label, "region": "Custom field", "state": None, "county": None,
        "lat": lat, "lon": lon, "area_ha": area_ha,
        "headline": "Built live from NASA POWER, GPM IMERG, MODIS, SRTM and the USDA soil survey for this coordinate.",
        "story": "This field was assembled on request from public data. Local yields, buyers, equipment and the baseline rotation are defaults until you correct them.",
        "challenge_tags": [],
        "management": {
            "irrigation": ({"type": "generic", "label": "Irrigated", "allocation_mm": allocation_mm, "sustainable_mm": 0.6 * allocation_mm,
                            "efficiency": 0.8, "cost_per_mm_acre": 0.4, "source": "user entry"} if irrigated else
                           {"type": "none", "label": "Rainfed", "allocation_mm": 0, "sustainable_mm": 0, "efficiency": 0, "cost_per_mm_acre": 0, "source": None}),
            "tillage": "conventional", "livestock": False, "custom_hire_available": True, "equipment": DEFAULT_EQUIPMENT,
            "tile_drained": False, "slope_length_m": 80, "erosivity_method": "rusle",
        },
        "baseline_rotation": baseline, "baseline_assumed": assumed,
        "water_context": {"aquifer": None, "in_situ_trend_m_yr": None, "in_situ_source": None,
                          "note": "No local water-level record on file. See USGS NWIS for nearby observation wells."},
        "reference_yields": {}, "local_market": {},
        "default_priorities": {"water": 6, "soil": 6, "erosion": 6, "pest": 5, "income": 6},
        "sources": ["NASA POWER", "GPM IMERG", "MODIS (ORNL DAAC)", "SRTM", "USDA SSURGO", "USDA CDL"],
    }
    field = {"id": field_id, "kind": "custom", "farm": farm, "obs": obs, "soil": soil}
    with _lock:
        _custom[field_id] = field
    if soil is not None:  # only a complete field is worth persisting across restarts
        cache.put("custom-field", field_id, field)
    return field
