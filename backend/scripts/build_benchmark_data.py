"""Pull real NASA / USDA observations for every benchmark farm and store them in data/.

    cd backend
    python -m scripts.build_benchmark_data            # all farms
    python -m scripts.build_benchmark_data palouse-wa # one farm

Writes:
    data/benchmark-farms/observations/<farm-id>.json   harmonised observation layers
    data/soil-profiles/<farm-id>.json                  SSURGO profile for the field

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


def build(farm_id: str) -> None:
    farm = json.loads((FARM_DIR / f"{farm_id}.json").read_text(encoding="utf-8"))
    t0 = time.time()
    obs = observe.collect(farm["lat"], farm["lon"], depth="full")
    soil = obs.pop("soil")
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
    wanted = sys.argv[1:] or sorted(p.stem for p in FARM_DIR.glob("*.json"))
    for farm_id in wanted:
        try:
            build(farm_id)
        except Exception as exc:  # keep going so one flaky service does not block the rest
            print(f"{farm_id}: FAILED {exc!r}")


if __name__ == "__main__":
    main()
