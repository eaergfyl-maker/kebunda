"""Monthly field simulation of one rotation.

One loop walks the rotation month by month and keeps five linked ledgers:

  cover     living canopy + decaying residue -> how exposed the soil is
  water     FAO-56 style bucket: rain - runoff (SCS curve number) - evaporation - transpiration
  erosion   RUSLE, with the cover-management factor computed from the cover ledger
  carbon    one-pool soil organic carbon balance (humified inputs vs. mineralisation)
  nitrogen  legume credits, fertiliser need and a residual-nitrate leaching ledger

Formulas, parameter sources and known weaknesses are documented in
docs/agronomy-models/. The models are deliberately simple and transparent: they rank
rotations against each other on one field; they do not predict a yield.
"""
from __future__ import annotations

import math

from app.services.rotation_engine.context import FieldContext, crops_by_id
from app.services.rotation_engine.schedule import Phase, Schedule, build_schedule, describe
from app.utils.geo import DAYS_IN_MONTH
from app.utils.stats import clamp, mean, normal_cdf, stdev

# Gauss-Laguerre nodes/weights (n=8) for the expected-runoff integral
_GL_X = [0.170279632305, 0.903701776799, 2.251086629866, 4.266700170288, 7.045905402393, 10.758516010181, 15.740678641278, 22.863131736889]
_GL_W = [3.69188589342e-01, 4.18786780814e-01, 1.75794986637e-01, 3.33434922612e-02, 2.79453623523e-03, 9.07650877336e-05, 8.48574671627e-07, 1.04800117487e-09]

# SCS curve numbers: bare tilled fallow vs. dense close-growing cover, by hydrologic soil group
CN_BARE = {"A": 77.0, "B": 86.0, "C": 91.0, "D": 94.0}
CN_COVERED = {"A": 51.0, "B": 67.0, "C": 76.0, "D": 80.0}

TILLAGE = {
    # *_keep: share of surface residue left after the operation; plu: RUSLE prior-land-use x
    # surface-roughness subfactors (buried residue, roots and clods slow runoff even on tilled soil);
    # k_mult: effect on organic-matter breakdown; cn_adj: curve-number shift from better structure
    "conventional": {"label": "Conventional tillage", "harvest_keep": 0.14, "plant_keep": 0.5, "fallow_keep": 0.80, "plu": 0.62, "k_mult": 1.25, "cn_adj": 0.0},
    "reduced": {"label": "Reduced / strip tillage", "harvest_keep": 0.75, "plant_keep": 0.6, "fallow_keep": 0.95, "plu": 0.50, "k_mult": 1.05, "cn_adj": -1.5},
    "no_till": {"label": "No-till", "harvest_keep": 1.0, "plant_keep": 0.92, "fallow_keep": 1.0, "plu": 0.38, "k_mult": 0.88, "cn_adj": -3.0},
}

N_PRICE_PER_KG = 1.20  # USD per kg N (about $0.55/lb)
ACRES_PER_HA = 2.4711
SOC_K0 = 0.0075  # yr-1 at 10 C under reduced tillage, calibrated to long-term rotation trials
HUMIFICATION_SHOOT, HUMIFICATION_ROOT = 0.13, 0.30
BARE_THRESHOLD = 0.30  # NRCS: under 30% cover is not conservation cover
PRICE_CORRELATION = 0.5
MAX_IRRIGATION_MM_MONTH = 330.0  # about 11 mm/day: what a well-designed system can deliver


def expected_runoff_per_wet_day(mean_depth_mm: float, cn: float) -> float:
    """E[Q] for exponentially distributed wet-day rainfall under the SCS-CN equation.

    Using the storm-size distribution rather than the monthly total is what lets the
    "storm intensity" slider matter: the same rain in fewer, bigger storms runs off more.
    """
    s = 25400.0 / cn - 254.0
    ia = 0.2 * s
    mu = max(0.5, mean_depth_mm)
    acc = 0.0
    for x, w in zip(_GL_X, _GL_W):
        excess = mu * x
        acc += w * excess * excess / (excess + s)
    return math.exp(-ia / mu) * acc


def heat_days(tmax_mean: float, tmax_sd: float, threshold: float, days: float) -> float:
    return days * (1.0 - normal_cdf((threshold - tmax_mean) / max(1.0, tmax_sd)))


def frost_days(tmin_mean: float, tmin_sd: float, days: float, threshold: float = 0.0) -> float:
    return days * normal_cdf((threshold - tmin_mean) / max(1.0, tmin_sd))


def _yield_scale(ctx: FieldContext, crop: dict) -> float:
    econ = crop.get("economics") or {}
    ref = econ.get("yield_ref") or 0
    local = ctx.reference_yields.get(crop["id"])
    return clamp(local / ref, 0.5, 1.5) if ref and local else 1.0


def _n_plan(ctx: FieldContext, sched: Schedule) -> dict[int, dict]:
    """Fertiliser N each harvested crop needs after legume and cover-crop credits."""
    plan: dict[int, dict] = {}
    order = list(range(len(sched.phases)))
    pending_credit = 0.0
    # walk the cycle twice so credits earned late in the rotation reach the first crop
    for _sweep in range(2):
        for i in order:
            ph = sched.phases[i]
            crop = ph.crop
            if ph.kind == "cover":
                pending_credit += crop["n_credit_kg_ha"] * ph.biomass_frac
                continue
            demand = crop["n_demand_kg_ha"] * _yield_scale(ctx, crop)
            credit = min(demand, pending_credit)
            plan[i] = {"demand": demand, "credit": credit, "applied": max(0.0, demand - credit)}
            pending_credit = crop["n_credit_kg_ha"] * (1.0 if ph.kind != "perennial" else 1.0)
    return plan


def simulate(ctx: FieldContext, years: list[list[str]], tillage: str = "conventional", *,
             with_history: bool = False) -> dict:
    crops = crops_by_id()
    cl = ctx.climate
    sched = build_schedule(years, crops, cl)
    till = TILLAGE.get(tillage, TILLAGE["conventional"])
    n_plan = _n_plan(ctx, sched)
    core = _run(ctx, sched, till, n_plan, cycles=3, year_indices=None)
    result = _summarise(ctx, sched, till, n_plan, core, years, tillage)
    if with_history and cl.years:
        result["history"] = _history(ctx, sched, till, n_plan, result)
    return result


def _run(ctx: FieldContext, sched: Schedule, till: dict, n_plan: dict, *, cycles: int,
         year_indices: list[int] | None, offset_years: int = 0, measure_from: int | None = None) -> dict:
    """Walk the rotation. With year_indices=None the climate normals repeat; otherwise each
    simulated year uses that historical year's weather."""
    cl, nm = ctx.climate, sched.n_months
    hsg = (ctx.soil.get("hydrologic_group") or "B")[0]
    if hsg not in CN_BARE:
        hsg = "B"
    if ctx.tile_drained and hsg in ("C", "D"):
        hsg = "B"  # tile drainage lets a wet soil behave like a better-drained one
    taw = ctx.taw_profile_mm
    depth = ctx.profile_depth_cm
    om = float(ctx.soil["organic_matter_pct"])
    k_ls = ctx.k_si * ctx.ls
    total_steps = (len(year_indices) * 12) if year_indices is not None else cycles * nm
    if measure_from is None:
        measure_from = total_steps - nm if year_indices is None else 0

    plant_at: dict[int, list[int]] = {}
    end_at: dict[int, list[int]] = {}
    kill_at: dict[int, list[int]] = {}
    for i, ph in enumerate(sched.phases):
        plant_at.setdefault(ph.plant % nm, []).append(i)
        end_at.setdefault(ph.end % nm, []).append(i)
        if ph.winterkilled_at is not None:
            kill_at.setdefault(ph.winterkilled_at % nm, []).append(i)

    s_water = taw * 0.6
    pools: list[list[float]] = []  # [mass t/ha, cover coefficient, monthly decay]
    n_pool = 20.0
    alloc_used: dict[int, float] = {}
    keys = ("cover", "canopy", "residue_cover", "runoff", "drainage", "soil_evap", "transp", "transp_pot",
            "irrigation", "soil_water_frac", "erosion", "n_leach", "precip", "et0")
    out = {k: [] for k in keys}
    out["occupant"] = []
    ph_tpot: dict[tuple[int, int], float] = {}
    ph_tact: dict[tuple[int, int], float] = {}
    ph_irr: dict[tuple[int, int], float] = {}

    for t in range(total_steps):
        rm = (t + offset_years * 12) % nm
        m = t % 12
        yi = year_indices[t // 12] if year_indices is not None else None
        precip, tmax, tmin, et0 = cl.month(m, yi)
        tmean = (tmax + tmin) / 2.0
        cycle_no = (t + offset_years * 12) // nm

        for i in plant_at.get(rm, []):
            ph = sched.phases[i]
            keep = 0.95 if ph.kind == "cover" else till["plant_keep"]
            for pool in pools:
                pool[0] *= keep
        for i in kill_at.get(rm, []):
            ph = sched.phases[i]
            pools.append([ph.crop["residue_t_ha"] * ph.biomass_frac, ph.crop["residue_cover_coef"], ph.crop["residue_decay_month"]])

        occ = sched.occupant[rm]
        canopy, green = sched.canopy[rm], sched.green[rm]
        f_t = clamp(tmean / 20.0, 0.03, 1.6)
        f_w = clamp(precip / max(1.0, 0.5 * et0), 0.3, 1.0)
        for pool in pools:
            pool[0] *= math.exp(-pool[2] * f_t * f_w)
        if occ is None and till["fallow_keep"] < 1.0 and tmean > 8.0:
            for pool in pools:
                pool[0] *= till["fallow_keep"]  # repeated summer-fallow tillage
        pools = [p for p in pools if p[0] > 0.02]
        res_cover = 1.0 - math.exp(-sum(p[0] * p[1] for p in pools))
        cover = 1.0 - (1.0 - canopy) * (1.0 - res_cover)

        # --- water -------------------------------------------------------------------
        cn = clamp(CN_BARE[hsg] - (CN_BARE[hsg] - CN_COVERED[hsg]) * cover + till["cn_adj"], 35.0, 98.0)
        wet_days = max(0.3, cl.wet_days[m])
        runoff = min(0.85 * precip, wet_days * expected_runoff_per_wet_day(precip / wet_days, cn)) if precip > 0 else 0.0
        infil = precip - runoff
        s_water += infil
        kc_soil = clamp(0.12 + 0.04 * wet_days, 0.12, 0.65) * (1.0 - 0.5 * res_cover)
        evap = min(kc_soil * et0 * (1.0 - canopy), 0.9 * infil + 0.08 * s_water, s_water)
        s_water -= evap
        t_pot = t_act = irr_gross = 0.0
        if occ is not None and green > 0:
            ph = sched.phases[occ]
            crop = ph.crop
            t_pot = crop["kc_mid"] * green * et0
            # Rain and irrigation wet the profile from the top down, so a crop reaches stored
            # water up to the capacity of its own root zone; deeper water needs deeper roots.
            reach = taw * clamp(crop["root_depth_m"] * 100.0 / depth, 0.2, 1.0)
            finishing = ph.kind == "cash" and rm == ph.maturity % nm  # last month: let the crop mine the profile
            thresh = 0.0 if finishing else (1.0 - crop["depletion_fraction"]) * reach
            if ctx.irrigated and ph.kind != "cover":
                year_key = t // 12
                remaining = max(0.0, ctx.allocation_mm - alloc_used.get(year_key, 0.0))
                need = max(0.0, t_pot + thresh - min(s_water, reach + infil))
                net = min(need, remaining * ctx.irrigation_efficiency, MAX_IRRIGATION_MM_MONTH)
                if net > 0:
                    irr_gross = net / ctx.irrigation_efficiency
                    alloc_used[year_key] = alloc_used.get(year_key, 0.0) + irr_gross
                    s_water += net
            # water arriving during the month (rain, irrigation) is usable as it arrives, so a
            # month's demand may exceed what the root zone holds at any one time
            avail = min(s_water, reach + infil + irr_gross * ctx.irrigation_efficiency)
            full = thresh + t_pot
            t_act = t_pot if avail >= full else t_pot * clamp(avail / max(1e-6, full))
            t_act = min(t_act, avail)
            s_water -= t_act
            key = (occ, cycle_no if ph.plant % nm <= rm else cycle_no - 1)
            ph_tpot[key] = ph_tpot.get(key, 0.0) + t_pot
            ph_tact[key] = ph_tact.get(key, 0.0) + t_act
            ph_irr[key] = ph_irr.get(key, 0.0) + irr_gross
        drainage = max(0.0, s_water - taw)
        s_water = min(s_water, taw)

        # --- erosion (RUSLE with a monthly soil-loss ratio) -----------------------------
        plu = till["plu"] * (0.8 if occ is not None else 1.0)
        if occ is not None and sched.phases[occ].kind == "perennial":
            plu = min(plu, 0.35)
        slr = plu * (1.0 - 0.85 * canopy) * math.exp(-3.5 * res_cover)
        erosion = cl.r_factor * cl.erosivity_share[m] * k_ls * slr

        # --- nitrogen residual pool -----------------------------------------------------
        n_pool += 2.5 * om * clamp(tmean / 20.0, 0.0, 1.5)
        if green > 0.1:
            n_pool -= min(n_pool, 45.0 * green)
        leach = n_pool * drainage / (drainage + 0.6 * taw) if drainage > 0 else 0.0
        n_pool -= leach

        for i in end_at.get(rm, []):
            ph = sched.phases[i]
            crop = ph.crop
            if ph.winterkilled_at is not None:
                continue
            if ph.kind == "cover":
                pools.append([crop["residue_t_ha"] * ph.biomass_frac, crop["residue_cover_coef"], crop["residue_decay_month"]])
                continue
            scale = _yield_scale(ctx, crop) * (ph.biomass_frac if ph.kind == "forage" else 1.0)
            pools.append([crop["residue_t_ha"] * scale, crop["residue_cover_coef"], crop["residue_decay_month"]])
            followed = sched.occupant[(rm + 1) % nm] is not None or sched.occupant[(rm + 2) % nm] is not None
            if not followed:
                for pool in pools:
                    pool[0] *= till["harvest_keep"]  # fall tillage only when nothing is seeded behind the combine
            plan = n_plan.get(i, {})
            n_pool += 0.22 * plan.get("applied", 0.0) + 0.4 * crop["n_credit_kg_ha"]

        if t >= measure_from:
            for k, v in zip(keys, (cover, canopy, res_cover, runoff, drainage, evap, t_act, t_pot, irr_gross,
                                   s_water / taw, erosion, leach, precip, et0)):
                out[k].append(v)
            out["occupant"].append(occ)

    out["phase_tpot"], out["phase_tact"], out["phase_irr"] = ph_tpot, ph_tact, ph_irr
    out["last_cycle"] = (total_steps - 1 + offset_years * 12) // nm
    return out


def _phase_yield(ctx: FieldContext, sched: Schedule, i: int, t_pot: float, t_act: float,
                 year_index: int | None = None, calendar_shift: int = 0) -> dict:
    """Relative yield of one harvested phase from water, heat, timing, soil-fit and rotation effects."""
    cl = ctx.climate
    ph = sched.phases[i]
    crop = ph.crop
    factors: dict[str, float] = {}
    ratio = t_act / t_pot if t_pot > 0 else 1.0
    factors["water"] = clamp(1.0 - crop["ky"] * (1.0 - ratio), 0.0, 1.0)

    span = max(1, ph.maturity - ph.plant + 1)
    lo, hi = ph.plant + int(0.4 * span), ph.plant + max(int(0.4 * span), math.ceil(0.85 * span) - 1)
    threshold = crop["heat_tmax_c"] + (1.0 if ctx.irrigated else 0.0)  # an irrigated canopy cools itself
    hd = hd_base = 0.0
    months = range(lo, hi + 1) if ph.kind != "perennial" else range(12)
    for m in months:
        cm = m % 12
        tmax = cl.tmax[cm] if year_index is None else cl.hist_tmax[year_index][cm]
        hd += heat_days(tmax, cl.tmax_sd[cm], threshold, DAYS_IN_MONTH[cm])
        hd_base += heat_days(cl.tmax_base[cm], cl.tmax_sd[cm], threshold, DAYS_IN_MONTH[cm])
    # A local reference yield already reflects today's normal heat, so only *extra* hot days
    # (a hot year, a warming scenario) cost yield. Crops without a local yield pay for all of them.
    counted = max(0.0, hd - hd_base) if crop["id"] in ctx.reference_yields else hd
    factors["heat"] = clamp(1.0 - crop["heat_loss_pct_per_day"] * counted / 100.0, 0.4, 1.0)
    factors["timing"] = clamp(1.0 - 0.08 * ph.delay_months, 0.6, 1.0)
    # Fixed site limits (salt, pH, drainage, humidity) are already inside a local reference
    # yield, so they are applied only to crops the farm has no local yield for.
    if crop["id"] not in ctx.reference_yields:
        ec = float(ctx.soil.get("ec_ds_m") or 0.0)
        factors["salinity"] = clamp(1.0 - 0.10 * max(0.0, ec - crop["salinity_threshold_ds_m"]), 0.5, 1.0)
        ph_soil = float(ctx.soil.get("ph") or 6.8)
        factors["ph"] = 0.9 if ph_soil < crop["ph_min"] - 0.2 or ph_soil > crop["ph_max"] + 0.2 else 1.0
        poorly = "poor" in (ctx.soil.get("drainage_class") or "").lower()
        factors["drainage"] = 0.88 if poorly and not crop["wet_feet_tolerant"] and not ctx.tile_drained else 1.0
        humid = sum(cl.precip) / max(1.0, sum(cl.et0)) > 0.75
        factors["humidity"] = 0.72 if humid and crop.get("humidity_sensitive") else 1.0  # foliar and root disease pressure

    mains = [k for k, p in enumerate(sched.phases) if p.kind != "cover"]
    prev = sched.phases[mains[mains.index(i) - 1]] if i in mains else ph
    back_to_back = sched.n_years == 1 if len(mains) == 1 else (prev.id == crop["id"] and (ph.year_index - prev.year_index) % sched.n_years == 1)
    if back_to_back and ph.kind != "perennial":
        factors["rotation"] = 0.90  # monoculture drag (e.g. corn after corn)
    elif prev.crop["legume"] and not crop["legume"] and prev is not ph:
        factors["rotation"] = 1.04
    else:
        factors["rotation"] = 1.0
    if ph.kind == "perennial":
        factors["establishment"] = (ph.stand_years - 0.5) / ph.stand_years if ph.stand_years < sched.n_years else 1.0
    if ph.kind == "forage":
        factors["growth_window"] = ph.biomass_frac
    rel = 1.0
    for v in factors.values():
        rel *= v
    return {"relative": rel, "factors": {k: round(v, 3) for k, v in factors.items()}, "heat_days": round(hd, 1)}


def _economics(ctx: FieldContext, sched: Schedule, n_plan: dict, yields: dict[int, dict], irr: dict[int, float]) -> dict:
    """Per-phase revenue and cost (USD per acre) for one pass through the rotation."""
    rows = []
    for i, ph in enumerate(sched.phases):
        crop, econ = ph.crop, ph.crop["economics"]
        irr_cost = irr.get(i, 0.0) * ctx.irrigation_cost_per_mm_acre
        if ph.kind == "cover":
            grazing = econ.get("grazing_value_per_acre", 0) * ph.biomass_frac if ctx.livestock else 0.0
            cost = econ["cost_per_acre"] if ph.biomass_frac > 0 else 0.0
            rows.append({"phase": i, "crop_id": ph.id, "crop_name": crop["name"], "kind": ph.kind, "yield": None, "yield_unit": None,
                         "relative_yield": None, "revenue": round(grazing, 0), "cost": round(cost, 0), "net": round(grazing - cost, 0),
                         "price": None, "price_cv": 0.0, "n_applied_kg_ha": 0.0, "irrigation_mm": 0.0})
            continue
        local = ctx.reference_yields.get(ph.id)
        ref = local if local else econ["yield_ref"]
        y = yields[i]
        span = ph.stand_years if ph.kind == "perennial" else 1
        actual = ref * y["relative"]
        n_applied = n_plan.get(i, {}).get("applied", 0.0) * span
        revenue = actual * econ["price"] * span
        cost = econ["cost_per_acre"] * span + n_applied / ACRES_PER_HA * N_PRICE_PER_KG + irr_cost
        rows.append({"phase": i, "crop_id": ph.id, "crop_name": crop["name"], "kind": ph.kind,
                     "yield": round(actual, 1 if actual < 1000 else 0), "yield_unit": econ["yield_unit"],
                     "relative_yield": round(y["relative"], 3), "yield_factors": y["factors"], "heat_days": y["heat_days"],
                     "local_reference": bool(local), "revenue": round(revenue, 0), "cost": round(cost, 0), "net": round(revenue - cost, 0),
                     "price": econ["price"], "price_cv": econ["price_cv"], "n_applied_kg_ha": round(n_applied, 0),
                     "irrigation_mm": round(irr.get(i, 0.0), 0)})
    return {"rows": rows, "gross": sum(r["revenue"] for r in rows), "cost": sum(r["cost"] for r in rows),
            "net": sum(r["net"] for r in rows)}


def _pest_metrics(sched: Schedule) -> dict:
    """Host-interval, functional-group and planting-season diversity (0-100)."""
    n = sched.n_years
    mains = [p for p in sched.phases if p.kind != "cover"]
    occurrences: dict[str, list[tuple[int, Phase, int]]] = {}
    for ph in mains:
        for year in range(ph.year_index, ph.year_index + ph.stand_years):
            for g in ph.crop["pest_groups"]:
                occurrences.setdefault(g["group"], []).append((year, ph, g["break_years"]))
    ratios, short = [], []
    for group, occ in occurrences.items():
        years_hit = sorted({y for y, _, _ in occ})
        for idx, (year, ph, brk) in enumerate(sorted(occ, key=lambda o: o[0])):
            if ph.kind == "perennial" and group == ph.crop["pest_groups"][0]["group"]:
                continue  # a perennial stand hosting itself is expected
            others = [y for y in years_hit if y != year]
            gap = min(((year - y) % n or n) for y in others) if others else n
            interval = gap if others else n  # years until the same host group returns
            ratio = clamp((interval - 1) / brk) if brk > 0 else 1.0
            ratios.append(ratio)
            if ratio < 1.0:
                short.append({"group": group, "crop_id": ph.id, "crop_name": ph.crop["name"],
                              "interval_years": interval, "recommended_years": brk + 1,
                              "named_pests": ph.crop.get("named_pests", [])[:3]})
    host = mean(ratios, 1.0)
    groups = {p.crop["functional_group"] for p in mains}
    cover_groups = {p.crop["functional_group"] for p in sched.phases if p.kind == "cover" and p.biomass_frac >= 0.2}
    group_score = clamp((len(groups) + 0.5 * len(cover_groups - groups) - 1) / 3.0)
    seasons = {("fall" if p.crop["cycle"] == "winter" else "perennial" if p.kind == "perennial" else
                "early_spring" if p.crop["t_plant_c"] < 9 else "late_spring") for p in mains}
    season_score = clamp((len(seasons) - 1) / 2.0)
    bridges = []
    for i, ph in enumerate(sched.phases):
        if ph.kind != "cover" or ph.biomass_frac <= 0:
            continue
        nxt = sched.phases[(i + 1) % len(sched.phases)]
        shared = {g["group"] for g in ph.crop["pest_groups"]} & {g["group"] for g in nxt.crop["pest_groups"]}
        if shared and nxt.kind != "cover":
            bridges.append({"cover": ph.crop["name"], "next_crop": nxt.crop["name"], "group": sorted(shared)[0]})
    # one entry per crop: its tightest host interval (a crop can share several pest groups)
    worst: dict[str, dict] = {}
    for s in short:
        cur = worst.get(s["crop_id"])
        if cur is None or s["interval_years"] / s["recommended_years"] < cur["interval_years"] / cur["recommended_years"]:
            worst[s["crop_id"]] = s
    short_unique = list(worst.values())
    score = 100.0 * (0.55 * host + 0.27 * group_score + 0.18 * season_score) - 6.0 * len(bridges)
    return {"score": clamp(score, 0.0, 100.0), "host_break_ratio": round(host, 2), "functional_groups": sorted(groups | cover_groups),
            "planting_seasons": sorted(seasons), "short_breaks": short_unique, "green_bridges": bridges,
            "distinct_cash_crops": len({p.id for p in mains})}


def _summarise(ctx: FieldContext, sched: Schedule, till: dict, n_plan: dict, core: dict,
               years: list[list[str]], tillage: str) -> dict:
    n, nm, cl = sched.n_years, sched.n_months, ctx.climate
    last = core["last_cycle"]

    def phase_total(d: dict, i: int) -> float:
        return d.get((i, last), 0.0) + (d.get((i, last - 1), 0.0) if (i, last) not in d else 0.0)

    yields, irr = {}, {}
    for i, ph in enumerate(sched.phases):
        if ph.kind == "cover":
            continue
        # a phase that wraps the cycle boundary is complete in the cycle where it was planted
        key_cycle = last - 1 if (ph.plant % nm) > (ph.end % nm) or (i, last) not in core["phase_tpot"] else last
        tp, ta = core["phase_tpot"].get((i, key_cycle), 0.0), core["phase_tact"].get((i, key_cycle), 0.0)
        yields[i] = _phase_yield(ctx, sched, i, tp, ta)
        irr[i] = core["phase_irr"].get((i, key_cycle), 0.0)
    econ = _economics(ctx, sched, n_plan, yields, irr)

    def per_year(key: str) -> float:
        return sum(core[key]) / n

    precip_yr = per_year("precip")
    irrigation = per_year("irrigation")
    cash_idx = {i for i, p in enumerate(sched.phases) if p.kind != "cover"}
    tp_cash = sum(v for (i, c), v in core["phase_tpot"].items() if i in cash_idx and c >= last - 1)
    ta_cash = sum(v for (i, c), v in core["phase_tact"].items() if i in cash_idx and c >= last - 1)
    stress = 1.0 - ta_cash / tp_cash if tp_cash > 0 else 0.0
    bare_months = sum(1 for c in core["cover"] if c < BARE_THRESHOLD) / n
    exposure = sum(cl.erosivity_share[t % 12] * (1.0 - core["cover"][t]) for t in range(nm)) / n
    living = sum(1 for t in range(nm) if sched.green[t] > 0.12 or sched.canopy[t] > 0.25) / n
    soil_loss = per_year("erosion")

    # carbon: humified inputs minus first-order mineralisation
    c_in_shoot = c_in_root = 0.0
    perennial_years = 0
    for i, ph in enumerate(sched.phases):
        crop = ph.crop
        if ph.kind == "cover":
            frac = root_frac = ph.biomass_frac
        else:
            frac = _yield_scale(ctx, crop) * yields[i]["relative"] ** 0.7 * (ph.biomass_frac if ph.kind == "forage" else 1.0)
            root_frac = max(frac, 0.3)
        span = ph.stand_years if ph.kind == "perennial" else 1
        perennial_years += span if ph.kind == "perennial" else 0
        c_in_shoot += crop["residue_t_ha"] * frac * 0.42 * span
        c_in_root += crop["root_t_ha"] * root_frac * 0.42 * span
    c_input = (c_in_shoot + c_in_root) / n
    humified = (c_in_shoot * HUMIFICATION_SHOOT + c_in_root * HUMIFICATION_ROOT) / n
    mat = mean(cl.tmean)
    clay = float(ctx.soil.get("clay_pct") or 22.0)
    wetness = clamp((precip_yr + irrigation) / max(1.0, sum(cl.et0)), 0.35, 1.0)
    pf = min(1.0, perennial_years / n)  # a standing perennial is untilled whatever the system
    k_mult = till["k_mult"] * (1.0 - pf) + min(till["k_mult"], TILLAGE["no_till"]["k_mult"]) * pf
    k = SOC_K0 * 2.0 ** ((mat - 10.0) / 10.0) * k_mult * (1.1 - 0.008 * clay) * (0.55 + 0.45 * wetness)
    soc = ctx.soc_stock_t_ha
    d_soc = humified - k * soc
    om_10yr = d_soc * 10.0 / (float(ctx.soil["bulk_density_g_cm3"]) * 30.0 * 100.0) * 1.724 * 100.0

    n_applied = sum(p["applied"] * (sched.phases[i].stand_years if sched.phases[i].kind == "perennial" else 1) for i, p in n_plan.items()) / n
    n_credit = sum(p["credit"] for p in n_plan.values()) / n
    n_demand = sum(p["demand"] for p in n_plan.values()) / n
    legume_years = sum(p.stand_years for p in sched.phases if p.kind != "cover" and p.crop["legume"])

    pests = _pest_metrics(sched)
    net_yr, gross_yr = econ["net"] / n, econ["gross"] / n
    price_sd = _price_sd(econ["rows"], n)
    market = _market_access(ctx, sched)
    needs = sorted({e for p in sched.phases if p.kind != "cover" for e in p.crop["equipment"]} - ctx.equipment)
    forage = mean([p.crop["forage_value"] for p in sched.phases]) if sched.phases else 0.0

    months = []
    for t in range(nm):
        occ = core["occupant"][t]
        months.append({
            "index": t, "calendar_month": t % 12, "year_index": t // 12,
            "crop_id": sched.phases[occ].id if occ is not None else None,
            "kind": sched.phases[occ].kind if occ is not None else None,
            "cover": round(core["cover"][t], 3), "canopy": round(core["canopy"][t], 3),
            "residue_cover": round(core["residue_cover"][t], 3), "green": round(sched.green[t], 3),
            "bare": core["cover"][t] < BARE_THRESHOLD,
            "runoff_mm": round(core["runoff"][t], 1), "drainage_mm": round(core["drainage"][t], 1),
            "transpiration_mm": round(core["transp"][t], 1), "demand_mm": round(core["transp_pot"][t], 1),
            "soil_evap_mm": round(core["soil_evap"][t], 1), "irrigation_mm": round(core["irrigation"][t], 1),
            "soil_water_frac": round(core["soil_water_frac"][t], 3), "erosion_t_ha": round(core["erosion"][t], 3),
            "n_leach_kg_ha": round(core["n_leach"][t], 2),
        })

    return {
        "years": years, "tillage": tillage, "n_years": n, "feasible": sched.feasible,
        "issues": sched.issues + [s for p in sched.phases for s in p.issues],
        "phases": describe(sched), "months": months,
        "metrics": {
            "irrigation_mm_yr": round(irrigation, 0),
            "allocation_used_pct": round(100.0 * irrigation / ctx.allocation_mm, 0) if ctx.allocation_mm > 0 else None,
            "crop_water_use_mm_yr": round(per_year("transp") + per_year("soil_evap"), 0),
            "transpiration_mm_yr": round(per_year("transp"), 0),
            "soil_evaporation_mm_yr": round(per_year("soil_evap"), 0),
            "runoff_mm_yr": round(per_year("runoff"), 0),
            "deep_drainage_mm_yr": round(per_year("drainage"), 0),
            "water_stress_pct": round(100.0 * stress, 1),
            "infiltration_pct": round(100.0 * (1.0 - per_year("runoff") / precip_yr), 1) if precip_yr > 0 else 100.0,
            "productive_water_pct": round(100.0 * per_year("transp") / max(1.0, precip_yr + irrigation), 1),
            "soil_loss_t_ha_yr": round(soil_loss, 2),
            "soil_loss_tons_ac_yr": round(soil_loss / 2.2417, 2),
            "soil_loss_vs_tolerable": round(soil_loss / ctx.t_factor_t_ha, 2),
            "bare_months_per_year": round(bare_months, 1),
            "mean_ground_cover_pct": round(100.0 * mean(core["cover"]), 0),
            "storm_exposure_pct": round(100.0 * exposure, 0),
            "living_root_months_per_year": round(living, 1),
            "carbon_input_t_ha_yr": round(c_input, 2),
            "soc_change_t_ha_yr": round(d_soc, 3),
            "om_change_pct_points_10yr": round(om_10yr, 2),
            "n_fertilizer_kg_ha_yr": round(n_applied, 0),
            "n_legume_credit_kg_ha_yr": round(n_credit, 0),
            "n_self_sufficiency_pct": round(100.0 * n_credit / n_demand, 0) if n_demand > 0 else 100.0,
            "n_leaching_kg_ha_yr": round(per_year("n_leach"), 1),
            "legume_years": legume_years,
            "pest_break_score": round(pests["score"], 0),
            "distinct_cash_crops": pests["distinct_cash_crops"],
            "net_return_per_acre_yr": round(net_yr, 0),
            "gross_revenue_per_acre_yr": round(gross_yr, 0),
            "cost_per_acre_yr": round(econ["cost"] / n, 0),
            "price_sd_per_acre": round(price_sd, 0),
            "market_access": round(market["score"], 2),
            "forage_value": round(forage, 2),
            "net_per_mm_irrigation": round(net_yr / irrigation, 2) if irrigation > 20 else None,
        },
        "pests": pests,
        "economics": econ["rows"],
        "market": market,
        "equipment_needed": needs,
    }


def _price_sd(rows: list[dict], n_years: int) -> float:
    """Income swing from prices alone, assuming every rotation phase is on the farm each year."""
    sds = [r["revenue"] / n_years * r["price_cv"] for r in rows if r.get("price_cv")]
    var = sum(s * s for s in sds) + PRICE_CORRELATION * (sum(sds) ** 2 - sum(s * s for s in sds))
    return math.sqrt(max(0.0, var))


def _market_access(ctx: FieldContext, sched: Schedule) -> dict:
    rows, scores = [], []
    for ph in sched.phases:
        if ph.kind == "cover":
            continue
        local = ctx.local_market.get(ph.id)
        access = local["access"] if local else ph.crop["market_default"]
        scores.append(access)
        rows.append({"crop_id": ph.id, "crop_name": ph.crop["name"], "access": access, "verified_locally": bool(local),
                     "note": local["note"] if local else "No local buyer information on file."})
    return {"score": min(scores) * 0.5 + mean(scores) * 0.5 if scores else 0.0, "rows": rows}


def _history(ctx: FieldContext, sched: Schedule, till: dict, n_plan: dict, normal: dict) -> dict:
    """Replay 2001-2024 weather through the rotation, once per rotation phase offset, so every
    crop meets every year. Gives real year-to-year swings instead of a guessed variability."""
    cl, n, nm = ctx.climate, sched.n_years, sched.n_months
    n_hist = len(cl.years)
    net_by_year = [0.0] * n_hist
    irr_by_year = [0.0] * n_hist
    stress_by_year = [0.0] * n_hist
    for offset in range(n):
        core = _run(ctx, sched, till, n_plan, cycles=0, year_indices=list(range(n_hist)), offset_years=offset)
        harvest_net: dict[int, float] = {}
        for (i, cyc), tp in core["phase_tpot"].items():
            ph = sched.phases[i]
            if ph.kind == "cover":
                continue
            if (ph.plant % nm) > (ph.end % nm):
                end_step = (cyc + 1) * nm + (ph.end % nm) - offset * 12
            else:
                end_step = cyc * nm + (ph.end % nm) - offset * 12
            hy = end_step // 12
            if not 0 <= hy < n_hist:
                continue
            y = _phase_yield(ctx, sched, i, tp, core["phase_tact"].get((i, cyc), 0.0), year_index=hy)
            rows = _economics(ctx, sched, n_plan, {k: y for k in range(len(sched.phases))}, {i: core["phase_irr"].get((i, cyc), 0.0)})["rows"]
            harvest_net[hy] = harvest_net.get(hy, 0.0) + rows[i]["net"]
        cover_cost = sum(r["net"] for r in normal["economics"] if r["kind"] == "cover") / n
        for hy in range(n_hist):
            net_by_year[hy] += (harvest_net.get(hy, 0.0) + cover_cost) / n
            irr_by_year[hy] += sum(core["irrigation"][hy * 12:(hy + 1) * 12]) / n
            tp = sum(core["transp_pot"][hy * 12:(hy + 1) * 12])
            ta = sum(core["transp"][hy * 12:(hy + 1) * 12])
            stress_by_year[hy] += (1.0 - ta / tp if tp > 0 else 0.0) / n
    usable = list(range(1, n_hist))  # the first year carries spin-up effects
    nets = [net_by_year[i] for i in usable]
    climate_sd = stdev(nets)
    price_sd = normal["metrics"]["price_sd_per_acre"]
    total_sd = math.sqrt(climate_sd**2 + price_sd**2)
    mean_net = mean(nets)
    order = sorted(usable, key=lambda i: net_by_year[i])
    return {
        "years": [cl.years[i] for i in usable],
        "net_per_acre": [round(net_by_year[i], 0) for i in usable],
        "irrigation_mm": [round(irr_by_year[i], 0) for i in usable],
        "water_stress_pct": [round(100 * stress_by_year[i], 1) for i in usable],
        "mean_net_per_acre": round(mean_net, 0),
        "weather_sd_per_acre": round(climate_sd, 0),
        "total_sd_per_acre": round(total_sd, 0),
        "bad_year_net_per_acre": round(mean_net - 0.84 * total_sd, 0),  # about a 1-in-5 year
        "worst_years": [cl.years[i] for i in order[:3]],
        "variability_ratio": round(total_sd / max(1.0, normal["metrics"]["gross_revenue_per_acre_yr"]), 3),
    }
