"""Regenerate the API contract files in docs/api-contracts/ from the running code.

    cd backend
    python -m scripts.export_contracts

Writes:
    openapi.json                 the full OpenAPI 3.1 schema (same as GET /openapi.json)
    examples/*.json              real request and response payloads for the Kedah (MADA paddy) benchmark farm

Run it whenever a route or schema changes, and commit the result with the change, so the
frontend can always develop and mock against files that match the backend exactly.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("ENVIRONMENT", "test")

from fastapi.testclient import TestClient  # noqa: E402

from app.config import REPO_ROOT  # noqa: E402
from app.main import app  # noqa: E402

OUT = REPO_ROOT / "docs" / "api-contracts"
FIELD = "kedah-mada"
API = "/api/v1"


def _write(name: str, payload) -> None:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(REPO_ROOT)} ({path.stat().st_size / 1024:.0f} kB)")


def _trim_strategy(s: dict) -> dict:
    """Keep the shape, shorten the long arrays so the example stays readable."""
    s = dict(s)
    s["months"] = s["months"][:3]
    s["vulnerability"] = {**s["vulnerability"], "cells": s["vulnerability"]["cells"][:3]}
    if s.get("history"):
        s["history"] = {**s["history"], **{k: s["history"][k][:4] for k in ("years", "net_per_ha", "irrigation_mm", "water_stress_pct")}}
    return s


def main() -> None:
    client = TestClient(app)
    _write("openapi.json", client.get("/openapi.json").json())

    _write("examples/farms.list.response.json", client.get(f"{API}/farms").json())
    overview = client.get(f"{API}/farms/{FIELD}").json()
    for key in ("precip", "wet_root", "wet_root_z", "heat_days_35", "tmax", "erosivity"):
        overview["series"][key] = overview["series"][key][:2]
    for key in ("vegetation", "surface_temperature", "evapotranspiration"):
        if overview.get(key):
            overview[key]["by_year"] = overview[key]["by_year"][:2]
    overview["fusion"]["precip_comparison"]["recent_months"] = overview["fusion"]["precip_comparison"]["recent_months"][:3]
    _write("examples/farm.overview.response.json", overview)

    request = {"field_id": FIELD, "priorities": {"water": 4, "soil": 8, "erosion": 9, "pest": 6, "income": 7},
               "constraints": {"risk_tolerance": "medium", "exclude_crops": []},
               "custom_strategies": [{"name": "My rotation", "years": [["rice", "mung_bean"], ["sweet_corn", "rice"]], "tillage": "reduced"}]}
    _write("examples/rotations.compare.request.json", request)
    compare = client.post(f"{API}/rotations/compare", json=request).json()
    specs = [{"id": s["id"], "role": s["role"], "name": s["name"], "years": s["years"], "tillage": s["tillage"]} for s in compare["strategies"]]
    compare["strategies"] = [_trim_strategy(s) for s in compare["strategies"][:2]]
    _write("examples/rotations.compare.response.json", compare)

    stress_request = {"field_id": FIELD, "strategies": specs[:3], "scenario": {"temp_delta_c": 2.0, "rain_pct": -20.0, "storm_intensity_pct": 10.0, "water_cap_pct": 100.0}}
    _write("examples/scenarios.stress-test.request.json", stress_request)
    stress = client.post(f"{API}/scenarios/stress-test", json=stress_request).json()
    for row in stress["strategies"]:
        row["phases"] = row["phases"][:2]
    _write("examples/scenarios.stress-test.response.json", stress)
    _write("examples/scenarios.sweep.response.json",
           client.post(f"{API}/scenarios/sweep", json={"field_id": FIELD, "strategies": specs[:3], "parameter": "rain_pct", "steps": 5}).json())

    vuln = client.get(f"{API}/farms/{FIELD}/vulnerability").json()
    vuln["baseline"]["calendar"]["cells"] = vuln["baseline"]["calendar"]["cells"][:3]
    _write("examples/farm.vulnerability.response.json", vuln)
    _write("examples/nasa.gibs-layers.response.json", client.get(f"{API}/nasa/gibs/layers").json())
    _write("examples/rotations.options.response.json", client.get(f"{API}/rotations/options").json())
    _write("examples/scenarios.presets.response.json", client.get(f"{API}/scenarios/presets").json())
    suit = client.get(f"{API}/soil-crops/suitability/{FIELD}").json()
    suit["rows"] = suit["rows"][:4]
    _write("examples/soil-crops.suitability.response.json", suit)
    _write("examples/error.response.json", client.get(f"{API}/farms/atlantis").json())


if __name__ == "__main__":
    main()
