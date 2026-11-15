"""Pull real NASA and global observations for every benchmark farm and store them in data/.

    cd backend
    python -m scripts.build_benchmark_data            # all farms
    python -m scripts.build_benchmark_data kedah-mada # one farm
    python -m scripts.build_benchmark_data --no-modis # skip MODIS when ORNL is down

Writes:
    data/benchmark-farms/observations/<farm-id>.json   harmonised observation layers
    data/soil-profiles/<farm-id>.json                  SoilGrids profile for the field, with any
                                                       `soil_overrides` from the farm file applied
                                                       (e.g. surveyed peat that the 250 m model misses)

Needs internet but no API keys. Re-running is cheap: raw responses are cached in data/cache/.
The service itself never needs this script at runtime; it reads the stored JSON.
"""
from __future__ import annotations

import json
import sys
import time

from app.config import settings
from app.services.fusion_engine import observe

FARM_DIR = settings.data_dir / "benchmark-farms"
OBS_DIR = FARM_DIR / "observations"
SOIL_DIR = settings.data_dir / "soil-profiles"


def build(farm_id: str, with_modis: bool = True) -> None:
    farm = json.loads((FARM_DIR / f"{farm_id}.json").read_text(encoding="utf-8"))
    t0 = time.time()
    irrigated = farm["management"]["irrigation"]["type"] != "none"
    obs = observe.collect(farm["lat"], farm["lon"], depth="full", irrigated=irrigated, with_modis=with_modis)
    soil = obs.pop("soil")
    overrides = farm.get("soil_overrides")
    if soil and overrides:
        soil.update({k: v for k, v in overrides.items() if k != "note"})
        soil["overrides_note"] = overrides.get("note")
        soil["derived"] = sorted(set(soil.get("derived", [])) | {k for k in overrides if k != "note"})
    obs["farm_id"] = farm_id
    OBS_DIR.mkdir(parents=True, exist_ok=True)
    (OBS_DIR / f"{farm_id}.json").write_text(json.dumps(obs, separators=(",", ":")), encoding="utf-8")
    if soil:
        soil["id"] = farm_id
        (SOIL_DIR / f"{farm_id}.json").write_text(json.dumps(soil, indent=2), encoding="utf-8")
    c = obs["climate"]
    print(
        f"{farm_id}: {time.time() - t0:.0f}s | P={c['annual_precip_mm']} mm  ET0={c['annual_et0_mm']} mm  "
        f"T={c['mean_annual_temp_c']} C | soil={soil and soil['series']} ({soil and soil['texture_class']}, "
        f"OM {soil and soil['organic_matter_pct']}%, HSG {soil and soil['hydrologic_group']}) | "
        f"slope={obs['terrain'] and obs['terrain']['slope_pct']}% | "
        f"ndvi={obs['ndvi'] and obs['ndvi']['monthly']} | issues={[i['layer'] for i in obs['issues']]}"
    )


def main() -> None:
    args = sys.argv[1:]
    with_modis = "--no-modis" not in args
    wanted = [a for a in args if not a.startswith("--")] or sorted(p.stem for p in FARM_DIR.glob("*.json"))
    for farm_id in wanted:
        try:
            build(farm_id, with_modis)
        except Exception as exc:  # keep going so one flaky service does not block the rest
            print(f"{farm_id}: FAILED {exc!r}")


if __name__ == "__main__":
    main()
