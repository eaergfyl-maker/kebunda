"""Top-level use cases the API exposes: field overview, rotation comparison, custom evaluation.

Glue only: the science lives in fusion_engine, rotation_engine, vulnerability_analyzer and
scenario_simulator.
"""
from __future__ import annotations

import threading
from collections import OrderedDict

from app.services import field_store
from app.services.fusion_engine import harmonize
from app.services.rotation_engine import engine, explain, scoring
from app.services.rotation_engine.context import NEUTRAL_SCENARIO, FieldContext, build_context, crops_by_id
from app.services.vulnerability_analyzer import calendar as vuln
from app.services.vulnerability_analyzer import insights as insight_mod
from app.utils.stats import mean

DISCLAIMER = ("FieldShift surfaces patterns and possibilities from public data. It supports, and never replaces, "
              "the judgment of the farmer and of local agronomists, Extension agents and crop advisers.")

_bundles: OrderedDict[str, dict] = OrderedDict()
_lock = threading.Lock()


class InvalidRotation(ValueError):
    pass


def bundle(field_id: str) -> dict:
    """Field + everything derived from its observations that does not depend on user input.
    Rebuilt automatically when the stored field is replaced (a custom field re-pulled)."""
    f = field_store.get_field(field_id)
    farm, obs, soil = f["farm"], f["obs"], f["soil"]
    with _lock:
        cached = _bundles.get(field_id)
    if cached is not None and cached["obs"] is obs:
        return cached
    fused = harmonize.fuse_precip(obs["precip_comparison"])
    layers = harmonize.layer_inventory(obs, soil, farm["area_ha"])
    conf = harmonize.confidence_by_dimension(layers, bool(farm.get("reference_yields")), bool(farm.get("local_market")))
    b = {**f, "fused_precip": fused, "layers": layers, "confidence": conf,
         "insights": insight_mod.field_insights(farm, obs, soil, fused)}
    with _lock:
        _bundles[field_id] = b
        while len(_bundles) > 24:
            _bundles.popitem(last=False)
    return b


def context(b: dict, scenario: dict | None = None, constraints: dict | None = None) -> FieldContext:
    return build_context(b["farm"], b["obs"], b["soil"], scenario=scenario, constraints=constraints,
                         precip_bias=b["fused_precip"]["bias_vs_merra2"], data_confidence=b["confidence"]["overall"])


def validate_years(years: list[list[str]]) -> list[list[str]]:
    crops = crops_by_id()
    if not 1 <= len(years) <= 6:
        raise InvalidRotation("A rotation must be 1 to 6 years long.")
    for y in years:
        if len(y) > 3:
            raise InvalidRotation("At most three crops per rotation year.")
        for cid in y:
            if cid not in crops:
                raise InvalidRotation(f"Unknown crop id '{cid}'. See GET /soil-crops/catalog.")
    if not any(years):
        raise InvalidRotation("A rotation needs at least one crop.")
    return years


def resolve_baseline(b: dict, override: dict | None) -> dict:
    base = dict(b["farm"]["baseline_rotation"])
    if override and override.get("years"):
        base = {"name": override.get("name") or "Your rotation", "years": validate_years(override["years"]),
                "tillage": override.get("tillage") or base.get("tillage", "conventional"), "note": "Entered by the user."}
    return base


def overview(field_id: str) -> dict:
    b = bundle(field_id)
    farm, obs, soil = b["farm"], b["obs"], b["soil"]
    ctx = context(b)
    c = obs["climate"]
    sm = harmonize.downscale_soil_moisture(c["monthly"]["wet_root"], ctx.soil, ctx.profile_depth_cm)
    return {
        "id": b["id"], "kind": b["kind"], "farm": farm, "soil": soil or ctx.soil, "terrain": obs.get("terrain"),
        "climate": {k: c[k] for k in ("years", "monthly", "frost", "annual", "trends", "drought_months_per_year",
                                      "annual_precip_mm", "annual_et0_mm", "mean_annual_temp_c", "aridity_index", "provenance")},
        "series": {"years": c["years"], "precip": c["by_year"]["precip"], "wet_root": c["by_year"]["wet_root"],
                   "wet_root_z": c["by_year"]["wet_root_z"], "heat_days_35": c["by_year"]["heat_days_35"],
                   "tmax": c["by_year"]["tmax"], "erosivity": c["by_year"]["erosivity"]},
        "vegetation": obs.get("ndvi"), "surface_temperature": obs.get("lst"), "evapotranspiration": obs.get("et"),
        "groundwater": {**(obs.get("grace") or {}), "local": farm.get("water_context")},
        "crop_history": obs.get("cdl"),
        "fusion": {
            "precip": b["fused_precip"], "precip_comparison": obs["precip_comparison"], "soil_moisture": sm,
            "soil_moisture_source": obs.get("soil_moisture"), "layers": b["layers"], "confidence": b["confidence"],
            "field_width_m": round((farm["area_ha"] * 10_000) ** 0.5, 0),
            "target_grid": "Calendar months at field scale (30 m reference grid of Landsat / SSURGO)",
        },
        "hazards": vuln.hazard_calendar(ctx, obs),
        "insights": b["insights"],
        "issues": obs.get("issues", []),
        "disclaimer": DISCLAIMER,
    }


def _explain_all(ctx: FieldContext, b: dict, strategies: list[dict], priorities: dict) -> list[dict]:
    base = strategies[0]
    ndvi_check = vuln.validate_against_ndvi(base, b["obs"])
    out = []
    for s in strategies:
        cal = vuln.strategy_calendar(ctx, s)
        s = dict(s)
        s["vulnerability"] = cal
        s["explanation"] = explain.build_explanation(ctx, s, base, priorities, b["insights"], b["layers"], b["confidence"], cal, ndvi_check)
        s["headline_numbers"] = _headline_numbers(ctx, s, base)
        out.append(s)
    out[0]["calendar_validation"] = ndvi_check
    return out


def _headline_numbers(ctx: FieldContext, s: dict, base: dict) -> list[dict]:
    m, bm = s["metrics"], base["metrics"]
    rows = []
    if ctx.irrigated:
        rows.append({"label": "Irrigation", "value": m["irrigation_mm_yr"], "unit": "mm/yr", "baseline": bm["irrigation_mm_yr"], "higher_is_better": False})
    else:
        rows.append({"label": "Crop water stress", "value": m["water_stress_pct"], "unit": "%", "baseline": bm["water_stress_pct"], "higher_is_better": False})
    rows += [
        {"label": "Bare soil", "value": m["bare_months_per_year"], "unit": "months/yr", "baseline": bm["bare_months_per_year"], "higher_is_better": False},
        {"label": "Soil erosion", "value": m["soil_loss_tons_ac_yr"], "unit": "tons/ac/yr", "baseline": bm["soil_loss_tons_ac_yr"], "higher_is_better": False},
        {"label": "Net return", "value": m["net_return_per_acre_yr"], "unit": "$/ac/yr", "baseline": bm["net_return_per_acre_yr"], "higher_is_better": True},
    ]
    return rows


def compare(field_id: str, priorities: dict | None = None, constraints: dict | None = None, scenario: dict | None = None,
            baseline_override: dict | None = None, custom_strategies: list[dict] | None = None) -> dict:
    b = bundle(field_id)
    constraints = constraints or {}
    priorities = {**scoring.DEFAULT_PRIORITIES, **(b["farm"].get("default_priorities") or {}), **(priorities or {})}
    baseline = resolve_baseline(b, baseline_override)
    if constraints.get("tillage"):
        baseline = {**baseline, "tillage": constraints["tillage"]}
    ctx = context(b, scenario, constraints)
    evaluated = engine.evaluate_candidates(field_id, ctx, baseline, constraints)
    strategies = engine.select_strategies(ctx, evaluated, priorities, constraints)
    base_final = strategies[0]
    for i, spec in enumerate(custom_strategies or []):
        years = validate_years(spec["years"])
        s = engine.finalise(ctx, "custom", years, spec.get("tillage") or baseline["tillage"], base_final, priorities, constraints)
        s["id"] = spec.get("id") or f"custom-{i + 1}"
        s["title"] = spec.get("name") or "Your own rotation"
        s["tagline"] = "Built by you in the sequence builder and scored with the same models."
        strategies.append(s)
    explained = _explain_all(ctx, b, strategies, priorities)
    ranked = sorted(explained, key=lambda s: -s["fit"]["fit"])
    for rank, s in enumerate(ranked, start=1):
        s["rank"] = rank
    top = ranked[0]
    tie = [s for s in ranked[1:] if top["fit"]["fit"] - s["fit"]["fit"] <= 3.0]
    return {
        "field_id": field_id, "field_name": b["farm"]["name"],
        "priorities": priorities, "priority_labels": scoring.DIMENSION_LABELS,
        "constraints": constraints, "scenario": ctx.scenario,
        "scenario_active": any(abs(float(ctx.scenario[k]) - float(NEUTRAL_SCENARIO[k])) > 1e-9 for k in NEUTRAL_SCENARIO),
        "baseline_note": baseline.get("note"), "baseline_assumed": b["farm"].get("baseline_assumed", False),
        "strategies": explained,
        "ranking": [s["id"] for s in ranked],
        "summary": {
            "top_id": top["id"],
            "statement": (f"\"{top['name']}\" fits your priorities best ({top['fit']['fit']:.0f}/100)."
                          + (f" It is effectively tied with {len(tie)} other option(s): the difference is inside the model's uncertainty." if tie else "")),
            "tied_ids": [s["id"] for s in tie],
            "baseline_fit": explained[0]["fit"]["fit"],
        },
        "search": {"crops_considered": evaluated["pool"], "rotations_screened": evaluated["n_screened"],
                   "rotations_simulated": evaluated["n_evaluated"]},
        "confidence": b["confidence"],
        "disclaimer": DISCLAIMER,
    }


def vulnerability(field_id: str, constraints: dict | None = None, scenario: dict | None = None) -> dict:
    """Hazard calendar plus the month-by-month risk grid of the field's current rotation."""
    from app.services.rotation_engine.simulate import simulate

    b = bundle(field_id)
    ctx = context(b, scenario, constraints)
    baseline = resolve_baseline(b, None)
    res = simulate(ctx, baseline["years"], baseline.get("tillage", "conventional"))
    return {
        "field_id": field_id,
        "hazards": vuln.hazard_calendar(ctx, b["obs"]),
        "hazard_labels": vuln.HAZARD_LABELS,
        "baseline": {"name": engine.rotation_name(baseline["years"]), "years": baseline["years"],
                     "tillage": baseline.get("tillage", "conventional"), "phases": res["phases"],
                     "calendar": vuln.strategy_calendar(ctx, res)},
        "validation": vuln.validate_against_ndvi(res, b["obs"]),
        "disclaimer": DISCLAIMER,
    }


def crop_suitability(field_id: str, constraints: dict | None = None) -> dict:
    from app.services.rotation_engine import generate

    b = bundle(field_id)
    ctx = context(b, None, constraints)
    rows = generate.suitability_screen(ctx, b["farm"]["baseline_rotation"].get("tillage", "conventional"))
    return {"field_id": field_id, "rows": rows,
            "method": ("Each crop is grown alone on this field in the model. Suitability is its relative yield after water, heat, "
                       "salinity, pH and drainage limits, in the spirit of FAO GAEZ suitability classes."),
            "mean_suitability": round(mean([r["suitability"] for r in rows if r["feasible"]], 0.0), 2)}


def warm_cache() -> None:
    """Pre-compute the default comparison for every benchmark farm so the first click is instant."""
    for fid in field_store.benchmark_ids():
        try:
            compare(fid)
        except Exception:  # noqa: BLE001 - warm-up must never stop the server from starting
            continue
