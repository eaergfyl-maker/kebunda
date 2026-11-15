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

DEFAULT_EQUIPMENT = ["hand_tractor", "knapsack_sprayer", "planter", "combine_hire"]


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
            "state": farm["state"], "district": farm.get("district"), "lat": farm["lat"], "lon": farm["lon"], "area_ha": farm["area_ha"],
            "headline": farm["headline"], "challenge_tags": farm["challenge_tags"],
            "baseline_name": farm["baseline_rotation"]["name"],
            "irrigation": farm["management"]["irrigation"]["label"],
            "annual_precip_mm": c["annual_precip_mm"], "mean_annual_temp_c": c["mean_annual_temp_c"],
            "soil_series": soil.get("series"), "soil_texture": soil.get("texture_class"),
            "organic_matter_pct": soil.get("organic_matter_pct"),
        })
    return out


def _baseline_from_cycles(cycles: dict | None, soil: dict | None, terrain: dict | None, irrigated: bool) -> dict | None:
    """Guess the current system from how many crop cycles a year Sentinel-2 sees.

    The satellite counts green-up and harvest cycles; it cannot name the crop. Flat, heavy,
    poorly drained land carrying two cycles is almost always double-cropped paddy in
    Malaysia; elsewhere the commonest smallholder annuals stand in. The note says so."""
    if not cycles or not cycles.get("years"):
        return None
    if cycles.get("evergreen"):
        return None  # oil palm, rubber or forest: not an annual-crop field
    n = cycles["cycles_per_year"]
    soil = soil or {}
    flat = (terrain or {}).get("slope_pct", 5.0) < 2.0
    heavy = soil.get("clay_pct", 0) >= 35 or soil.get("hydrologic_group") == "D"
    paddy_land = flat and heavy
    if n >= 1.6:
        years = [["rice", "rice"]] if paddy_land else [["sweet_corn", "long_bean"]]
        name = "Double-cropped paddy" if paddy_land else "Two vegetable crops a year"
    elif n >= 0.6:
        years = [["rice"]] if paddy_land else [["sweet_corn"]]
        name = "One paddy season a year" if paddy_land else "One crop a year"
    else:
        return None
    return {"name": f"{name} (from Sentinel-2 crop cycles)", "years": years, "tillage": "conventional",
            "note": (f"Sentinel-2 counted about {n:.1f} crop cycles a year here. The crops themselves are assumed from the land "
                     "type; edit them, and the tillage, to match your records.")}


def create_custom_field(lat: float, lon: float, name: str | None = None, area_ha: float = 40.0,
                        irrigated: bool = False, allocation_mm: float = 400.0) -> dict:
    """Pull live NASA and global layers for a coordinate and assemble a field the engines can run on."""
    field_id = "custom-" + hashlib.sha1(f"{lat:.4f},{lon:.4f},{irrigated},{allocation_mm:.0f},{area_ha:.1f}".encode()).hexdigest()[:10]
    try:
        existing = get_field(field_id)
        if existing["soil"] is not None:  # a field built without its soil layer is rebuilt on the next request
            if name and existing["farm"]["name"] != name:
                existing["farm"]["name"] = existing["farm"]["short_name"] = name
            return existing
    except FieldNotFound:
        pass
    obs = observe.collect(lat, lon, depth="fast", irrigated=irrigated)  # raises ConnectorError if NASA POWER is unreachable
    soil = obs.pop("soil")
    baseline = _baseline_from_cycles(obs.get("crop_cycles"), soil, obs.get("terrain"), irrigated)
    assumed = baseline is None
    if assumed:
        baseline = {
            "name": "Assumed baseline: sweet corn, then long bean",
            "years": [["sweet_corn", "long_bean"]], "tillage": "conventional",
            "note": ("Sentinel-2 could not resolve annual crop cycles here (cloud, a perennial crop or a mixed pixel), so a common "
                     "smallholder vegetable sequence was assumed. Replace it with your real rotation."),
        }
    label = name or f"Field at {abs(lat):.3f}°{'N' if lat >= 0 else 'S'}, {abs(lon):.3f}°{'E' if lon >= 0 else 'W'}"
    farm = {
        "id": field_id, "name": label, "short_name": label, "region": "Custom field", "state": None, "district": None,
        "lat": lat, "lon": lon, "area_ha": area_ha,
        "headline": "Built live from NASA POWER, GPM IMERG, SRTM, Sentinel-2, SoilGrids and FAO GAEZ for this coordinate.",
        "story": "This field was assembled on request from public data. Local yields, buyers, equipment and the baseline rotation are defaults until you correct them.",
        "challenge_tags": [],
        "management": {
            "irrigation": ({"type": "generic", "label": "Irrigated", "allocation_mm": allocation_mm, "sustainable_mm": 0.6 * allocation_mm,
                            "efficiency": 0.7, "cost_per_mm_ha": 1.0, "source": "user entry"} if irrigated else
                           {"type": "none", "label": "Rainfed", "allocation_mm": 0, "sustainable_mm": 0, "efficiency": 0, "cost_per_mm_ha": 0, "source": None}),
            "tillage": "conventional", "livestock": False, "custom_hire_available": True, "equipment": DEFAULT_EQUIPMENT,
            "tile_drained": False, "slope_length_m": 80, "erosivity_method": "rusle",
        },
        "baseline_rotation": baseline, "baseline_assumed": assumed,
        "water_context": {"aquifer": None, "in_situ_trend_m_yr": None, "in_situ_source": None,
                          "note": "No local water record on file. JPS (Department of Irrigation and Drainage) publishes river and reservoir levels."},
        "reference_yields": {}, "local_market": {},
        "default_priorities": {"water": 6, "soil": 6, "erosion": 6, "pest": 5, "income": 6},
        "sources": ["NASA POWER", "GPM IMERG", "SRTM", "Copernicus Sentinel-2", "ISRIC SoilGrids", "FAO GAEZ v4", "NOAA GHCN-Daily"],
    }
    field = {"id": field_id, "kind": "custom", "farm": farm, "obs": obs, "soil": soil}
    with _lock:
        _custom[field_id] = field
    if soil is not None:  # only a complete field is worth persisting across restarts
        cache.put("custom-field", field_id, field)
    return field
