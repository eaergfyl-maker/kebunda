"""Candidate rotation generator.

Two stages keep it fast enough to feel interactive:
  1. screen every crop for this field (does it mature? does it survive winter? how does it
     yield with this soil, water and heat?), then enumerate 2-4 year cash-crop sequences
     from the crops that fit;
  2. take the sequences that do best on any one decision dimension and expand them with
     cover-crop and tillage variants.

Everything is simulated with the same models as the baseline, so no option is scored on a
reputation it has not earned on this field.
"""
from __future__ import annotations

from itertools import product

from app.services.rotation_engine.context import FieldContext, crops_by_id
from app.services.rotation_engine.schedule import build_schedule
from app.services.rotation_engine.simulate import simulate
from app.utils.stats import mean

MAX_POOL = 7
LEGUME_COVERS = ["hairy_vetch", "crimson_clover", "winter_pea"]
SUITABILITY_CLASSES = [(0.80, "Very suitable"), (0.62, "Suitable"), (0.45, "Moderately suitable"), (0.0, "Marginal")]


def suitability_screen(ctx: FieldContext, tillage: str) -> list[dict]:
    """GAEZ-style agro-climatic and soil fit for every harvestable crop on this field."""
    rows = []
    for crop in crops_by_id().values():
        if crop["role"] == "cover":
            continue
        years = [[crop["id"]]] * (3 if crop["cycle"] == "perennial" else 1)
        sim = simulate(ctx, years, tillage)
        econ = [e for e in sim["economics"] if e["kind"] != "cover"]
        factors = dict(econ[0].get("yield_factors", {})) if econ else {}
        factors.pop("rotation", None)  # grown alone here only to test fit; monoculture drag is not a site limit
        factors.pop("establishment", None)
        rel = 1.0
        for v in factors.values():
            rel *= v
        rel = rel if sim["feasible"] else 0.0
        limiting = sorted((k for k, v in factors.items() if v < 0.93 and k != "rotation"), key=lambda k: factors[k])
        missing = sorted(set(crop["equipment"]) - ctx.equipment)
        local = ctx.local_market.get(crop["id"])
        rows.append({
            "crop_id": crop["id"], "name": crop["name"], "family": crop["family"], "role": crop["role"],
            "feasible": sim["feasible"],
            "suitability": round(rel, 2),
            "suitability_class": "Not suited" if not sim["feasible"] else next(lbl for thr, lbl in SUITABILITY_CLASSES if rel >= thr),
            "limiting_factors": limiting,
            "reasons": sim["issues"][:2],
            "relative_yield_factors": factors,
            "net_return_per_acre": sim["metrics"]["net_return_per_acre_yr"] if sim["feasible"] else None,
            "irrigation_mm": sim["metrics"]["irrigation_mm_yr"],
            "water_use_mm": sim["metrics"]["crop_water_use_mm_yr"],
            "plant_month": sim["phases"][0]["plant_calendar_month"] if sim["phases"] else None,
            "harvest_month": sim["phases"][0]["end_calendar_month"] if sim["phases"] else None,
            "market_access": local["access"] if local else crop["market_default"],
            "market_verified": bool(local),
            "has_local_yield": crop["id"] in ctx.reference_yields,
            "equipment_missing": missing,
            "drought_tolerance": crop["drought_tolerance"], "legume": crop["legume"], "deep_rooted": crop["deep_rooted"],
        })
    rows.sort(key=lambda r: (-int(r["feasible"]), -r["suitability"]))
    return rows


def _canonical(seq: tuple) -> tuple:
    rots = [seq[i:] + seq[:i] for i in range(len(seq))]
    return min(rots)


def main_signature(years: list[list[str]]) -> tuple:
    """The harvested-crop sequence, ignoring covers and where the cycle starts."""
    crops = crops_by_id()
    seq = tuple(tuple(c for i, c in enumerate(y) if crops[c]["role"] != "cover" and not (i > 0 and crops[c]["role"] == "forage")) for y in years)
    return _canonical(seq)


def pick_pool(ctx: FieldContext, screen: list[dict], baseline_years: list[list[str]], constraints: dict) -> list[str]:
    exclude = set(constraints.get("exclude_crops") or [])
    base = {c for y in baseline_years for c in y}
    scored = []
    for row in screen:
        cid = row["crop_id"]
        if cid in exclude or not row["feasible"] or row["role"] == "forage":
            continue
        if row["equipment_missing"] and not ctx.custom_hire and cid not in base:
            continue
        # an unconfirmed buyer counts for less than one the farm file documents
        market = row["market_access"] * (1.0 if row["market_verified"] else 0.7)
        if cid not in base and (row["suitability"] < 0.45 or market < 0.33):
            continue
        # blend agronomic fit, the money and whether anyone will buy it
        value = row["suitability"] * 0.45 + market * 0.30 + min(1.0, max(0.0, (row["net_return_per_acre"] or 0) / 400.0)) * 0.25
        scored.append((cid in base, value, cid))
    scored.sort(reverse=True)
    pool = [cid for _b, _v, cid in scored][:MAX_POOL]
    for cid in constraints.get("must_include_crops") or []:
        if cid in crops_by_id() and cid not in pool and cid not in exclude:
            pool.append(cid)
    return pool


def base_sequences(pool: list[str], baseline_years: list[list[str]], allow_fallow: bool, max_years: int) -> list[list[list[str]]]:
    """Cash-crop sequences of 2..max_years with no crop following itself."""
    crops = crops_by_id()
    tokens = list(pool) + (["__fallow__"] if allow_fallow else [])
    seen, out = set(), []
    for length in range(2, max_years + 1):
        for seq in product(tokens, repeat=length):
            if any(seq[i] == seq[(i + 1) % length] for i in range(length)):
                continue
            if seq.count("__fallow__") > 1:
                continue
            if any(length % d == 0 and seq == seq[:d] * (length // d) for d in range(1, length)):
                continue  # ABAB is just AB written twice
            perennials = [c for c in seq if c != "__fallow__" and crops[c]["cycle"] == "perennial"]
            if perennials:
                continue  # perennial stands are added as dedicated templates below
            key = _canonical(seq)
            if key in seen:
                continue
            seen.add(key)
            out.append([[] if c == "__fallow__" else [c] for c in key])
    for cid in pool:
        if crops[cid]["cycle"] == "perennial":
            others = [c for c in pool if c != cid][:3]
            for a in others:
                out.append([[cid], [cid], [cid], [a]])
                for b in others:
                    if a != b:
                        out.append([[cid], [cid], [cid], [a], [b]])
    return out


def _winter_hardy(ctx: FieldContext, cid: str) -> bool:
    hardy = crops_by_id()[cid].get("min_winter_tmin_c")
    return hardy is None or min(ctx.climate.tmin) >= hardy


def add_covers(ctx: FieldContext, years: list[list[str]], style: str) -> list[list[str]] | None:
    """Fill every off-season gap of 3+ months with a cover chosen for what follows it.

    style = "cover": grass before legumes, legume-containing mix before nitrogen-hungry crops.
    style = "forage": winter triticale wherever a harvestable forage fits (second income).
    """
    crops = crops_by_id()
    cl = ctx.climate
    sched = build_schedule(years, crops, cl)
    nm = sched.n_months
    mains = sorted((p for p in sched.phases if p.kind != "cover"), key=lambda p: p.plant)
    if not mains:
        return None
    legume_cover = next((c for c in LEGUME_COVERS if _winter_hardy(ctx, c)), None)
    out = [list(y) for y in years]
    changed = False
    for i, ph in enumerate(mains):
        nxt = mains[(i + 1) % len(mains)]
        gap = (nxt.plant - ph.end - 1) % nm if len(mains) > 1 else nm - (ph.end - ph.plant + 1)
        if gap < 3 or ph.kind == "perennial":
            continue
        end_cal = ph.end % 12
        summer_gap = cl.tmean[(end_cal + 1) % 12] > 20 and cl.tmean[(end_cal + 2) % 12] > 18 and gap >= 4
        if style == "forage":
            choice = "triticale" if _winter_hardy(ctx, "triticale") else None
            if choice and nxt.crop["cycle"] == "winter":
                choice = None  # no room for a winter forage ahead of a fall-sown crop
        elif summer_gap and nxt.crop["cycle"] == "winter" and sum(cl.precip[(end_cal + k) % 12] for k in (1, 2, 3)) > 150:
            choice = "sorghum_sudan"
        elif nxt.crop["legume"] or not legume_cover:
            choice = "cereal_rye"
        elif nxt.crop["n_demand_kg_ha"] >= 150 and gap >= 6:
            choice = legume_cover if min(cl.tmin) > -8 else "cover_mix"
        else:
            choice = "cover_mix"
        if choice and choice not in out[ph.year_index % len(out)]:
            # a multi-year stand lists its cover on the stand's last year
            year = (ph.year_index + ph.stand_years - 1) % len(out)
            out[year] = out[year] + [choice]
            changed = True
    return out if changed else None


def variants(ctx: FieldContext, years: list[list[str]], base_tillage: str, constraints: dict) -> list[tuple[list[list[str]], str]]:
    """Cover-crop and tillage variants of one cash sequence."""
    allow_cover = constraints.get("allow_cover_crops", True)
    allow_till = constraints.get("allow_tillage_change", True)
    order = ["conventional", "reduced", "no_till"]
    tills = [base_tillage]
    if allow_till and base_tillage != "no_till":
        tills.append(order[min(2, order.index(base_tillage) + 1)])
        if base_tillage == "conventional":
            tills.append("no_till")
    out = [(years, t) for t in tills]
    if allow_cover:
        covered = add_covers(ctx, years, "cover")
        if covered:
            out += [(covered, t) for t in tills]
        forage = add_covers(ctx, years, "forage") if (ctx.livestock or ctx.local_market.get("triticale", {}).get("access", 0) >= 0.8) else None
        if forage and "hay_equipment" in (ctx.equipment | ({"hay_equipment"} if ctx.custom_hire else set())):
            out += [(forage, t) for t in tills[:2]]
    return out
