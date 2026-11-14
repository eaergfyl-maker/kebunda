"""What-if stress tests.

A scenario does not re-rank from a lookup table. It changes the climate inputs
(temperature, rain total, storm size, water cap) and re-runs the same crop calendar,
water balance, erosion, carbon and economics models, including the 24-year weather replay.
So a +2 C scenario can move a planting date, add heat days at flowering, raise reference
ET, exhaust an irrigation allocation in July and show up as a lower bad-year income, all
through the physics rather than through a hand-set penalty.
"""
from __future__ import annotations

from app.services import analysis
from app.services.rotation_engine import engine, scoring
from app.services.rotation_engine.context import NEUTRAL_SCENARIO, FieldContext
from app.services.rotation_engine.simulate import frost_days, heat_days, simulate
from app.utils.geo import DAYS_IN_MONTH
from app.utils.stats import r

LIMITS = {
    "temp_delta_c": {"min": -1.0, "max": 5.0, "step": 0.5, "unit": "°C", "label": "Warmer growing seasons",
                     "plain": "Shifts every month's temperatures. Changes planting dates, heat days, frost days and how thirsty the air is."},
    "rain_pct": {"min": -50.0, "max": 30.0, "step": 5.0, "unit": "%", "label": "More or less rain",
                 "plain": "Scales yearly rain and snow. Same number of storms, each one bigger or smaller."},
    "storm_intensity_pct": {"min": 0.0, "max": 60.0, "step": 5.0, "unit": "%", "label": "Rain arriving in heavier bursts",
                            "plain": "The same total rain falls in fewer, heavier storms. More runs off, less soaks in, and bare soil erodes faster."},
    "water_cap_pct": {"min": 0.0, "max": 100.0, "step": 5.0, "unit": "% of allocation", "label": "Irrigation water you can pump",
                      "plain": "Cuts the irrigation allocation. 100% is today's allocation; 0% is no irrigation at all."},
}

PRESETS = [
    {"id": "today", "label": "Today's climate", "description": "The 2001-2024 record as observed.", "scenario": dict(NEUTRAL_SCENARIO)},
    {"id": "hot_dry_summer", "label": "Hot, dry decade", "description": "A run of years like 2012 or 2022: 2 C warmer, a fifth less rain.",
     "scenario": {"temp_delta_c": 2.0, "rain_pct": -20.0, "storm_intensity_pct": 10.0, "water_cap_pct": 100.0}},
    {"id": "water_cut", "label": "Allocation cut by 40%", "description": "A groundwater plan or a dry-year curtailment trims pumping.",
     "scenario": {"temp_delta_c": 0.5, "rain_pct": 0.0, "storm_intensity_pct": 0.0, "water_cap_pct": 60.0}},
    {"id": "gully_washers", "label": "Fewer, heavier storms", "description": "Same rain in bigger bursts, as the heaviest-day trend suggests.",
     "scenario": {"temp_delta_c": 1.0, "rain_pct": 5.0, "storm_intensity_pct": 40.0, "water_cap_pct": 100.0}},
    {"id": "mid_century", "label": "Mid-century outlook", "description": "A plausible 2050s combination: warmer, slightly drier, stormier, less water to pump.",
     "scenario": {"temp_delta_c": 2.5, "rain_pct": -10.0, "storm_intensity_pct": 25.0, "water_cap_pct": 75.0}},
]

KEY_METRICS = ["irrigation_mm_yr", "water_stress_pct", "soil_loss_tons_ac_yr", "bare_months_per_year", "runoff_mm_yr",
               "net_return_per_acre_yr", "soc_change_t_ha_yr", "crop_water_use_mm_yr"]


def clean_scenario(raw: dict | None) -> dict:
    sc = dict(NEUTRAL_SCENARIO)
    for key, lim in LIMITS.items():
        if raw and raw.get(key) is not None:
            sc[key] = max(lim["min"], min(lim["max"], float(raw[key])))
    return sc


def climate_shift(base: FieldContext, shifted: FieldContext) -> dict:
    """What the scenario does to the field's weather, in numbers a farmer recognises."""
    def totals(ctx: FieldContext) -> dict:
        cl = ctx.climate
        return {
            "annual_precip_mm": r(sum(cl.precip), 0), "reference_et_mm": r(sum(cl.et0), 0),
            "heat_days_35": r(sum(heat_days(cl.tmax[m], cl.tmax_sd[m], 35.0, DAYS_IN_MONTH[m]) for m in range(12)), 0),
            "frost_days": r(sum(frost_days(cl.tmin[m], cl.tmin_sd[m], DAYS_IN_MONTH[m]) for m in range(12)), 0),
            "erosivity_r": r(cl.r_factor, 0), "rain_per_wet_day_mm": r(sum(cl.precip) / max(1.0, sum(cl.wet_days)), 1),
            "irrigation_allocation_mm": r(ctx.allocation_mm, 0) if ctx.irrigated or base.irrigated else None,
        }
    a, b = totals(base), totals(shifted)
    return {k: {"today": a[k], "scenario": b[k], "delta": None if a[k] is None or b[k] is None else r(b[k] - a[k], 1)} for k in a}


def _evaluate(ctx: FieldContext, specs: list[dict], priorities: dict, constraints: dict) -> list[dict]:
    base_spec = next((s for s in specs if s.get("role") == "baseline"), specs[0])
    base_res = simulate(ctx, base_spec["years"], base_spec.get("tillage", "conventional"), with_history=True)
    out = []
    for spec in specs:
        res = base_res if spec is base_spec else simulate(ctx, spec["years"], spec.get("tillage", "conventional"), with_history=True)
        res = dict(res)
        res["scores"] = scoring.dimension_scores(ctx, res, base_res)
        res["fit"] = scoring.fit_score(res["scores"], priorities, res, base_res, constraints)
        res["spec"] = spec
        out.append(res)
    return out


def _normalise(b: dict, strategies: list[dict]) -> list[dict]:
    """Validate crop ids and fill a missing tillage with the field's own system."""
    default = b["farm"]["baseline_rotation"].get("tillage", "conventional")
    out = []
    for i, s in enumerate(strategies):
        analysis.validate_years(s["years"])
        out.append({**s, "tillage": s.get("tillage") or default, "id": s.get("id") or f"strategy-{i + 1}"})
    return out


def stress_test(field_id: str, strategies: list[dict], scenario: dict | None, priorities: dict | None = None,
                constraints: dict | None = None) -> dict:
    """Run the given strategies under today's climate and under the scenario, side by side."""
    b = analysis.bundle(field_id)
    constraints = constraints or {}
    priorities = {**scoring.DEFAULT_PRIORITIES, **(b["farm"].get("default_priorities") or {}), **(priorities or {})}
    sc = clean_scenario(scenario)
    strategies = _normalise(b, strategies)
    ctx0 = analysis.context(b, None, constraints)
    ctx1 = analysis.context(b, sc, constraints)
    today = _evaluate(ctx0, strategies, priorities, constraints)
    future = _evaluate(ctx1, strategies, priorities, constraints)
    rows = []
    for t, f in zip(today, future):
        spec = t["spec"]
        flags = list(dict.fromkeys(f["issues"]))
        if not f["feasible"]:
            flags.insert(0, "This rotation no longer fits the season under this scenario.")
        m0, m1 = t["metrics"], f["metrics"]
        if m1.get("allocation_used_pct") and m1["allocation_used_pct"] >= 99 and m1["water_stress_pct"] > m0["water_stress_pct"] + 5:
            flags.append("The irrigation allocation runs out before crop demand is met.")
        if m1["soil_loss_vs_tolerable"] > 1.0 >= m0["soil_loss_vs_tolerable"]:
            flags.append("Soil loss rises above the tolerable rate.")
        yields = []
        for e0, e1 in zip(t["economics"], f["economics"]):
            if e0["kind"] != "cover" and e0["yield"]:
                yields.append({"crop_id": e0["crop_id"], "crop_name": e0["crop_name"], "today": e0["yield"], "scenario": e1["yield"],
                               "unit": e0["yield_unit"], "change_pct": r((e1["yield"] - e0["yield"]) / e0["yield"] * 100, 0),
                               "limiting": min(e1["yield_factors"], key=lambda k: e1["yield_factors"][k]) if e1.get("yield_factors") else None})
        fit0, fit1 = t["fit"]["fit"], f["fit"]["fit"]
        rows.append({
            "id": spec.get("id"), "role": spec.get("role"), "name": spec.get("name") or engine.rotation_name(spec["years"]),
            "years": spec["years"], "tillage": spec.get("tillage", "conventional"), "feasible": f["feasible"],
            "fit": {"today": fit0, "scenario": fit1, "delta": r(fit1 - fit0, 1)},
            "scores": {d: {"today": t["scores"][d], "scenario": f["scores"][d], "delta": r(f["scores"][d] - t["scores"][d], 1)} for d in scoring.DIMENSIONS},
            "metrics": {k: {"today": m0[k], "scenario": m1[k], "delta": r(m1[k] - m0[k], 2)} for k in KEY_METRICS if m0.get(k) is not None and m1.get(k) is not None},
            "bad_year_net_per_acre": {"today": t["history"]["bad_year_net_per_acre"], "scenario": f["history"]["bad_year_net_per_acre"]} if t.get("history") and f.get("history") else None,
            "yields": yields, "flags": flags,
            "net_retained_pct": r(100 * m1["net_return_per_acre_yr"] / m0["net_return_per_acre_yr"], 0) if m0["net_return_per_acre_yr"] > 50 else None,
            "phases": f["phases"],
        })
    order0 = [x["id"] for x in sorted(rows, key=lambda x: -x["fit"]["today"])]
    order1 = [x["id"] for x in sorted(rows, key=lambda x: (not x["feasible"], -x["fit"]["scenario"]))]
    steadiest = min(rows, key=lambda x: abs(x["metrics"]["net_return_per_acre_yr"]["delta"]) if x["feasible"] else 1e9)
    best = next(x for x in rows if x["id"] == order1[0])
    verdict = (f"Under this scenario \"{best['name']}\" comes out ahead"
               + (" (it also leads today)." if order0[0] == order1[0] else f"; today the leader is \"{next(x['name'] for x in rows if x['id'] == order0[0])}\".")
               + f" Net return moves least for \"{steadiest['name']}\".")
    return {
        "field_id": field_id, "scenario": sc, "limits": LIMITS,
        "climate_shift": climate_shift(ctx0, ctx1),
        "strategies": rows, "ranking_today": order0, "ranking_scenario": order1,
        "ranking_changed": order0 != order1, "verdict": verdict,
        "note": "Scenarios shift the observed 2001-2024 record; they are stress tests, not forecasts.",
        "disclaimer": analysis.DISCLAIMER,
    }


def sweep(field_id: str, strategies: list[dict], parameter: str, priorities: dict | None = None,
          constraints: dict | None = None, steps: int = 7, base_scenario: dict | None = None) -> dict:
    """Vary one scenario dial across its range to find where rotations trade places."""
    if parameter not in LIMITS:
        raise analysis.InvalidRotation(f"Unknown scenario parameter '{parameter}'.")
    b = analysis.bundle(field_id)
    constraints = constraints or {}
    priorities = {**scoring.DEFAULT_PRIORITIES, **(b["farm"].get("default_priorities") or {}), **(priorities or {})}
    lim = LIMITS[parameter]
    strategies = _normalise(b, strategies)
    steps = max(3, min(11, steps))
    # snap to the dial's own step so the chart shows values a farmer could set
    raw = [lim["min"] + (lim["max"] - lim["min"]) * i / (steps - 1) for i in range(steps)]
    values = sorted({round(round(v / lim["step"]) * lim["step"], 2) for v in raw})
    series = {s.get("id") or str(i): {"id": s.get("id"), "name": s.get("name") or engine.rotation_name(s["years"]), "fit": [], "net": [], "feasible": []}
              for i, s in enumerate(strategies)}
    for v in values:
        sc = clean_scenario({**(base_scenario or {}), parameter: v})
        res = _evaluate(analysis.context(b, sc, constraints), strategies, priorities, constraints)
        for i, x in enumerate(res):
            key = x["spec"].get("id") or str(i)
            series[key]["fit"].append(x["fit"]["fit"])
            series[key]["net"].append(x["metrics"]["net_return_per_acre_yr"])
            series[key]["feasible"].append(x["feasible"])
    crossings = []
    ids = list(series)
    for i in range(1, len(values)):
        lead_prev = max(ids, key=lambda k: series[k]["fit"][i - 1])
        lead_now = max(ids, key=lambda k: series[k]["fit"][i])
        if lead_prev != lead_now:
            crossings.append({"between": [values[i - 1], values[i]], "from": series[lead_prev]["name"], "to": series[lead_now]["name"]})
    return {"field_id": field_id, "parameter": parameter, "label": lim["label"], "unit": lim["unit"], "values": values,
            "series": list(series.values()), "crossings": crossings}
