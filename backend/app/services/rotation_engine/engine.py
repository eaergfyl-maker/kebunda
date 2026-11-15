"""Rotation engine orchestration: evaluate candidates once, re-rank instantly.

The expensive part (simulating a few hundred rotations) depends on the field, the climate
scenario and the hard constraints, but NOT on the farmer's priority weights. So the
candidate set is cached per (field, scenario, constraints) and moving a priority slider
only re-ranks it.
"""
from __future__ import annotations

import json
import threading
from collections import OrderedDict

from app.services.rotation_engine import generate, scoring
from app.services.rotation_engine.context import FieldContext, crops_by_id
from app.services.rotation_engine.simulate import TILLAGE, simulate
from app.utils.geo import MONTH_NAMES

_CACHE: OrderedDict[str, dict] = OrderedDict()
_CACHE_MAX = 48
_LOCK = threading.Lock()
STAGE2_PER_DIMENSION = 10

ROLE_META = {
    "baseline": {"title": "What you do now", "tagline": "Your current rotation, scored the same way as every alternative."},
    "step": {"title": "Same crops, covered soil", "tagline": "Keep the crops you know. Change what happens between them."},
    "match": {"title": "Best match for your priorities", "tagline": "The rotation that scores highest for what you told us matters most."},
    "resilient": {"title": "Most resilient", "tagline": "The most diverse option: built for soil health and bad years, not for the best year."},
    "income": {"title": "Protect the bottom line", "tagline": "The strongest net return that still improves on today."},
}


def _slim(result: dict) -> dict:
    return {k: v for k, v in result.items() if k != "months"}


def _cache_key(field_key: str, ctx: FieldContext, baseline: dict, constraints: dict) -> str:
    relevant = {k: constraints.get(k) for k in ("exclude_crops", "must_include_crops", "allow_cover_crops",
                                                "allow_tillage_change", "max_rotation_years", "allow_fallow")}
    soil = [ctx.soil.get("series"), ctx.soil.get("organic_matter_pct"), round(ctx.taw_profile_mm)]
    return json.dumps([field_key, ctx.scenario, ctx.irrigated, round(ctx.allocation_mm), sorted(ctx.equipment),
                       ctx.custom_hire, ctx.livestock, round(ctx.slope_pct, 1), soil, baseline, relevant], sort_keys=True, default=str)


def evaluate_candidates(field_key: str, ctx: FieldContext, baseline: dict, constraints: dict) -> dict:
    """Simulate the baseline and every generated candidate. Cached."""
    key = _cache_key(field_key, ctx, baseline, constraints)
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    base_tillage = baseline.get("tillage", "conventional")
    base_result = simulate(ctx, baseline["years"], base_tillage, with_history=True)
    screen = generate.suitability_screen(ctx, base_tillage)
    pool = generate.pick_pool(ctx, screen, baseline["years"], constraints)
    has_fallow = any(len(y) == 0 for y in baseline["years"])
    allow_fallow = constraints.get("allow_fallow", has_fallow)
    max_years = int(constraints.get("max_rotation_years") or 4)
    if generate.is_tropical(ctx.climate):
        months = {r["crop_id"]: r["season_months"] or 12 for r in screen}
        sequences = generate.tropical_sequences(pool, months, allow_fallow, max(1, min(2, max_years)))
    else:
        sequences = generate.base_sequences(pool, baseline["years"], allow_fallow, max(2, min(5, max_years)))

    stage1 = []
    for years in sequences:
        res = simulate(ctx, years, base_tillage)
        if not res["feasible"]:
            continue
        res["scores"] = scoring.dimension_scores(ctx, res, base_result)
        stage1.append(res)
    keep: dict[str, dict] = {}
    for dim in scoring.DIMENSIONS + ["_equal"]:
        ranked = sorted(stage1, key=lambda r: -(sum(r["scores"].values()) if dim == "_equal" else r["scores"][dim]))
        for res in ranked[:STAGE2_PER_DIMENSION]:
            keep[json.dumps(res["years"])] = res
    # the baseline's own crop sequence always goes through stage 2 (cover and tillage variants)
    seeds = [r["years"] for r in keep.values()] + [[[c for c in y if crops_by_id()[c]["role"] != "cover"] for y in baseline["years"]]]

    candidates: dict[str, dict] = {}
    for years in seeds:
        for var_years, till in generate.variants(ctx, years, base_tillage, constraints):
            sig = json.dumps([var_years, till])
            if sig in candidates or (var_years == baseline["years"] and till == base_tillage):
                continue
            res = simulate(ctx, var_years, till)
            if not res["feasible"]:
                continue
            res["scores"] = scoring.dimension_scores(ctx, res, base_result)
            candidates[sig] = _slim(res)
    base_result["scores"] = scoring.dimension_scores(ctx, base_result, base_result)
    payload = {"baseline": base_result, "candidates": list(candidates.values()), "screen": screen, "pool": pool,
               "n_screened": len(sequences), "n_evaluated": len(candidates) + len(stage1)}
    with _LOCK:
        _CACHE[key] = payload
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
    return payload


def _crop_set(result: dict) -> frozenset:
    return frozenset(p["crop_id"] for p in result["phases"] if p["kind"] != "cover")


def select_strategies(ctx: FieldContext, evaluated: dict, priorities: dict, constraints: dict, limit: int = 5) -> list[dict]:
    """Pick the baseline plus up to four clearly different alternatives."""
    base = evaluated["baseline"]
    base_sig = generate.main_signature(base["years"])
    ranked = []
    for cand in evaluated["candidates"]:
        fit = scoring.fit_score(cand["scores"], priorities, cand, base, constraints)
        ranked.append({**cand, "fit": fit})
    ranked.sort(key=lambda c: -c["fit"]["fit"])
    chosen: list[tuple[str, dict]] = []

    def distinct(c: dict) -> bool:
        return all(json.dumps([c["years"], c["tillage"]]) != json.dumps([o["years"], o["tillage"]]) and
                   not (generate.main_signature(c["years"]) == generate.main_signature(o["years"]) and role != "step" and
                        generate.main_signature(o["years"]) != base_sig)
                   for role, o in chosen)

    same_crops = [c for c in ranked if generate.main_signature(c["years"]) == base_sig]
    if same_crops:
        chosen.append(("step", same_crops[0]))
    different = [c for c in ranked if generate.main_signature(c["years"]) != base_sig]
    for c in different:
        if distinct(c):
            chosen.append(("match", c))
            break
    resilience = sorted(
        (c for c in different if c["metrics"]["distinct_cash_crops"] >= 3 and c["scores"]["income"] >= 30),
        key=lambda c: -(c["scores"]["soil"] + c["scores"]["erosion"] + c["scores"]["pest"] + c["scores"]["water"]))
    for c in resilience:
        if distinct(c) and all(_crop_set(c) != _crop_set(o) for _r, o in chosen):
            chosen.append(("resilient", c))
            break
    earners = sorted((c for c in different if c["fit"]["weighted_score"] >= scoring.fit_score(base["scores"], priorities, base, base, constraints)["weighted_score"] - 2),
                     key=lambda c: -c["metrics"]["net_return_per_ha_yr"])
    for c in earners:
        if distinct(c) and all(_crop_set(c) != _crop_set(o) for _r, o in chosen):
            chosen.append(("income", c))
            break
    # never return fewer than two alternatives: top up from the ranked list
    for c in ranked:
        if len(chosen) >= 2:
            break
        if distinct(c):
            chosen.append(("match", c))

    out = [finalise(ctx, "baseline", base["years"], base["tillage"], base, priorities, constraints, precomputed=base)]
    for role, cand in chosen[: limit - 1]:
        out.append(finalise(ctx, role, cand["years"], cand["tillage"], base, priorities, constraints))
    return out


def finalise(ctx: FieldContext, role: str, years: list[list[str]], tillage: str, base: dict, priorities: dict,
             constraints: dict, precomputed: dict | None = None) -> dict:
    """Full-detail simulation (with the 24-year weather replay) plus scores for one strategy."""
    res = precomputed or simulate(ctx, years, tillage, with_history=True)
    res = dict(res)
    res["scores"] = scoring.dimension_scores(ctx, res, base)
    res["fit"] = scoring.fit_score(res["scores"], priorities, res, base, constraints)
    res["role"] = role
    res["id"] = role if role == "baseline" else f"{role}-{abs(hash(json.dumps([years, tillage]))) % 10**8:08d}"
    res["title"] = ROLE_META.get(role, ROLE_META["match"])["title"]
    res["tagline"] = ROLE_META.get(role, ROLE_META["match"])["tagline"]
    res["name"] = rotation_name(years)
    res["tillage_label"] = TILLAGE[tillage]["label"]
    res["year_labels"] = year_labels(years)
    return res


def rotation_name(years: list[list[str]]) -> str:
    crops = crops_by_id()
    parts = []
    i = 0
    while i < len(years):
        y = years[i]
        if not y:
            parts.append("Fallow")
            i += 1
            continue
        span = 1
        while i + span < len(years) and years[i + span] == y and crops[y[0]]["cycle"] == "perennial":
            span += 1
        names = [_short(crops[c]["name"]) for c in y]
        label = " + ".join(names)
        parts.append(f"{label} ({span} yr)" if span > 1 else label)
        i += span
    if len(parts) > 1:
        return " → ".join(parts)
    if len(years) == 1 and len(years[0]) > 1 and crops[years[0][0]]["cycle"] != "perennial":
        return f"{parts[0]}, every year"  # two or three crops chained through each year
    if crops[years[0][0]]["cycle"] == "perennial" if years and years[0] else False:
        return f"{parts[0]}, replanted"
    return f"Continuous {parts[0][:1].lower()}{parts[0][1:]}"


def _short(name: str) -> str:
    """Display name without the bracketed local name or note: "Paddy rice (irrigated)" -> "Paddy rice"."""
    if not name:
        return name
    base = name.split(" (")[0].replace(" cover", "").replace(" green manure", "").strip()
    return base[:1].upper() + base[1:]


def year_labels(years: list[list[str]]) -> list[dict]:
    crops = crops_by_id()
    return [{"year": i + 1, "crops": [{"id": c, "name": crops[c]["name"], "role": crops[c]["role"], "family": crops[c]["family"],
                                         "functional_group": crops[c]["functional_group"], "legume": crops[c]["legume"]} for c in y],
             "fallow": not y} for i, y in enumerate(years)]


def month_range(months: list[int]) -> str:
    """Human label for a set of calendar months, e.g. [10, 11, 0, 1] -> 'Nov-Feb'."""
    if not months:
        return "no months"
    s = sorted(set(months))
    if len(s) == 12:
        return "all year"
    runs, cur = [], [s[0]]
    for m in s[1:]:
        if m == cur[-1] + 1:
            cur.append(m)
        else:
            runs.append(cur)
            cur = [m]
    runs.append(cur)
    if len(runs) > 1 and runs[0][0] == 0 and runs[-1][-1] == 11:
        runs[0] = runs.pop() + runs[0]
    return ", ".join(MONTH_NAMES[r[0]] if len(r) == 1 else f"{MONTH_NAMES[r[0]]}-{MONTH_NAMES[r[-1]]}" for r in runs)
