"""Turn simulated metrics into five 0-100 scores and one priority-weighted fit.

Scores use fixed, documented anchors (not "best of the candidates = 100"), so a number
means the same thing on every field and does not jump when a new option is added.
Income is the one exception: its profit term is measured against the field's own baseline,
because a good net return in dryland wheat and in processing tomatoes differ by 20x.
"""
from __future__ import annotations

from app.services.rotation_engine.context import FieldContext
from app.utils.stats import clamp, lerp_score

DIMENSIONS = ["water", "soil", "erosion", "pest", "income"]
DIMENSION_LABELS = {
    "water": "Save water and ride out drought",
    "soil": "Build organic matter and nitrogen",
    "erosion": "Keep soil covered and in place",
    "pest": "Break pest, weed and disease cycles",
    "income": "Income, forage and markets",
}
DEFAULT_PRIORITIES = {d: 5.0 for d in DIMENSIONS}
RISK_FACTORS = {"low": 1.0, "medium": 0.4, "high": 0.0}


def variability(result: dict) -> float:
    """Income swing as a share of gross revenue. Uses the 24-year weather replay when present."""
    hist = result.get("history")
    if hist:
        return hist["variability_ratio"]
    m = result["metrics"]
    gross = max(1.0, m["gross_revenue_per_acre_yr"])
    return m["price_sd_per_acre"] / gross + 0.5 * m["water_stress_pct"] / 100.0


def dimension_scores(ctx: FieldContext, result: dict, baseline: dict) -> dict[str, float]:
    m, b = result["metrics"], baseline["metrics"]
    irr = ctx.farm.get("management", {}).get("irrigation") or {}
    if ctx.irrigated:
        sustainable = float(irr.get("sustainable_mm") or 0.6 * ctx.allocation_mm) or 1.0
        water = (0.55 * lerp_score(m["irrigation_mm_yr"] / sustainable, 1.8, 0.4)
                 + 0.25 * lerp_score(m["water_stress_pct"], 35, 3)
                 + 0.20 * lerp_score(m["productive_water_pct"], 30, 75))
    else:
        water = (0.50 * lerp_score(m["water_stress_pct"], 45, 5)
                 + 0.30 * lerp_score(m["productive_water_pct"], 20, 65)
                 + 0.20 * lerp_score(m["infiltration_pct"], 70, 98))
    soil = (0.40 * lerp_score(m["soc_change_t_ha_yr"], -0.35, 0.45)
            + 0.20 * lerp_score(m["n_self_sufficiency_pct"], 0, 60)
            + 0.20 * lerp_score(m["living_root_months_per_year"], 3.5, 11)
            + 0.10 * lerp_score(m["n_leaching_kg_ha_yr"], 40, 3)
            + 0.10 * lerp_score(m["infiltration_pct"], 70, 98))
    erosion = (0.50 * lerp_score(m["soil_loss_vs_tolerable"], 2.0, 0.15)
               + 0.30 * lerp_score(m["bare_months_per_year"], 7.5, 0.5)
               + 0.20 * lerp_score(m["storm_exposure_pct"], 80, 15))
    pest = float(m["pest_break_score"])
    scale = max(150.0, abs(b["net_return_per_acre_yr"]), 0.25 * b["gross_revenue_per_acre_yr"])
    rel = (m["net_return_per_acre_yr"] - b["net_return_per_acre_yr"]) / scale
    profit = 50.0 + 50.0 * clamp(rel / 0.6, -1.0, 1.0)
    forage = lerp_score(m["forage_value"], 0.0, 0.6) if ctx.livestock else 50.0
    income = (0.45 * profit + 0.25 * lerp_score(variability(result), 0.45, 0.10)
              + 0.20 * lerp_score(m["market_access"], 0.3, 1.0) + 0.10 * forage)
    return {"water": round(water, 1), "soil": round(soil, 1), "erosion": round(erosion, 1),
            "pest": round(pest, 1), "income": round(income, 1)}


def change_load(result: dict, baseline: dict) -> dict:
    """How much the farmer has to change: new crops, cover crops, a tillage system, equipment."""
    base_crops = {c for y in baseline["years"] for c in y}
    crops = {p["crop_id"] for p in result["phases"] if p["kind"] != "cover"}
    covers = {p["crop_id"] for p in result["phases"] if p["kind"] == "cover"} - base_crops
    new = sorted(crops - base_crops)
    tillage_change = result["tillage"] != baseline["tillage"]
    load = len(new) + (1 if covers else 0) + (1 if tillage_change else 0) + 0.5 * len(result["equipment_needed"])
    return {"new_crops": new, "adds_cover_crops": bool(covers), "tillage_change": tillage_change,
            "equipment_needed": result["equipment_needed"], "load": load}


def fit_score(scores: dict[str, float], priorities: dict[str, float], result: dict, baseline: dict,
              constraints: dict) -> dict:
    weights = {d: max(0.0, float(priorities.get(d, 5.0))) for d in DIMENSIONS}
    total = sum(weights.values()) or 1.0
    weighted = sum(scores[d] * weights[d] for d in DIMENSIONS) / total
    load = change_load(result, baseline)
    risk = RISK_FACTORS.get(constraints.get("risk_tolerance", "medium"), 0.4)
    penalties = []
    if load["equipment_needed"]:
        penalties.append({"reason": "Needs equipment not on the farm", "points": 3.0 * len(load["equipment_needed"])})
    if risk > 0 and load["load"] > 0:
        penalties.append({"reason": "Amount of change versus your risk tolerance", "points": round(3.0 * risk * load["load"], 1)})
    if risk > 0 and result["metrics"]["market_access"] < 0.75:
        penalties.append({"reason": "Thin or unverified local market", "points": round(10.0 * risk * (0.75 - result["metrics"]["market_access"]) / 0.75, 1)})
    fit = clamp(weighted - sum(p["points"] for p in penalties), 0.0, 100.0)
    return {"fit": round(fit, 1), "weighted_score": round(weighted, 1), "penalties": penalties,
            "weights": {d: round(weights[d] / total, 3) for d in DIMENSIONS}, "change": load}
