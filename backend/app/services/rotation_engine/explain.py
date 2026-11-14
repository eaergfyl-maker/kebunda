"""The five things the challenge asks every strategy to explain:

    1. why it was suggested          4. information gaps and model uncertainty
    2. what evidence supports it     5. risks that need local review
    3. the expected benefits

Every sentence is assembled from numbers the models produced for this field, so the
explanation can never drift from the scores. Nothing here is free text from a language
model: if a claim appears, the value behind it is in the payload next to it.
"""
from __future__ import annotations

from app.services.rotation_engine.context import FieldContext, crops_by_id, load_catalog
from app.services.rotation_engine.engine import month_range
from app.services.rotation_engine.scoring import DIMENSION_LABELS, DIMENSIONS

WHO_FARMER, WHO_EXT, WHO_CCA = "Farmer", "County Extension", "Certified Crop Adviser"
WHO_BUYER, WHO_INSURER, WHO_NRCS, WHO_WATER = "Buyer / elevator", "Crop insurance agent", "NRCS field office", "Water district / well driller"

RESIDUAL_HERBICIDE_CROPS = {"corn", "sorghum", "winter_wheat", "spring_wheat", "barley", "soybean", "cotton"}
SENSITIVE_FOLLOWERS = {"canola", "sunflower", "dry_pea", "chickpea", "lentil", "alfalfa", "tomato", "safflower", "oats",
                       "radish", "crimson_clover", "hairy_vetch", "winter_pea", "cover_mix"}


def _fmt(v: float, unit: str) -> str:
    if unit.startswith("$"):
        return f"${v:,.0f}{unit[1:]}"
    if unit == "%":
        return f"{v:,.1f}%" if abs(v) < 10 and not float(v).is_integer() else f"{v:,.0f}%"
    if abs(v) >= 100 or float(v).is_integer():
        return f"{v:,.0f} {unit}".strip()
    return f"{v:,.1f} {unit}".strip() if abs(v) >= 1 else f"{v:.2f} {unit}".strip()


# metric id, label, unit, higher-is-better, dimension, plain-language meaning
BENEFIT_SPECS = [
    ("irrigation_mm_yr", "Irrigation pumped", "mm/yr", False, "water", "Water applied per year, averaged over the rotation."),
    ("crop_water_use_mm_yr", "Total crop water use", "mm/yr", False, "water", "Evaporation plus transpiration from the field."),
    ("water_stress_pct", "Crop water stress", "%", False, "water", "Share of crop water demand the soil and irrigation could not meet."),
    ("om_change_pct_points_10yr", "Organic matter after 10 years", "% points", True, "soil", "Projected change in topsoil organic matter."),
    ("n_fertilizer_kg_ha_yr", "Purchased nitrogen", "kg N/ha/yr", False, "soil", "Fertiliser nitrogen needed after legume and cover-crop credits."),
    ("n_leaching_kg_ha_yr", "Nitrogen lost below roots", "kg N/ha/yr", False, "soil", "Residual nitrate carried down by drainage."),
    ("infiltration_pct", "Rain that soaks in", "%", True, "erosion", "Share of rainfall that enters the soil instead of running off."),
    ("soil_loss_tons_ac_yr", "Soil erosion", "tons/ac/yr", False, "erosion", "RUSLE sheet-and-rill soil loss."),
    ("bare_months_per_year", "Months with bare soil", "months/yr", False, "erosion", "Months with under 30% ground cover."),
    ("living_root_months_per_year", "Months with living roots", "months/yr", True, "soil", "Months something is growing and feeding soil life."),
    ("pest_break_score", "Pest and disease break", "/100", True, "pest", "Years between host crops, plant-family and planting-season diversity."),
    ("net_return_per_acre_yr", "Net return", "$/ac/yr", True, "income", "Revenue minus operating, nitrogen, irrigation and cover-crop costs. Land cost excluded."),
]


def _direction(delta: float, higher_better: bool, tol: float) -> str:
    if abs(delta) <= tol:
        return "same"
    return "better" if (delta > 0) == higher_better else "worse"


def benefits(strategy: dict, baseline: dict, confidence: dict) -> list[dict]:
    """Quantified change against the current rotation, including the trade-offs."""
    out = []
    m, b = strategy["metrics"], baseline["metrics"]
    for key, label, unit, higher, dim, meaning in BENEFIT_SPECS:
        v, bv = m.get(key), b.get(key)
        if v is None or bv is None:
            continue
        if key == "irrigation_mm_yr" and v == 0 and bv == 0:
            continue
        delta = v - bv
        tol = max(0.03 * abs(bv), 0.05 if "pct_points" in key or "tons" in key else 0.5)
        pct = delta / abs(bv) * 100 if abs(bv) > 1e-6 else None
        conf = confidence[dim]["combined"]
        band = (1 - conf) * 0.9  # relative half-width of the plausible range around the change
        out.append({
            "metric": key, "label": label, "unit": unit, "dimension": dim, "meaning": meaning,
            "baseline": bv, "value": v, "delta": round(delta, 2), "delta_pct": round(pct, 0) if pct is not None else None,
            "direction": _direction(delta, higher, tol), "confidence": confidence[dim]["label"],
            "range": [round(delta * (1 - band), 2), round(delta * (1 + band), 2)] if abs(delta) > tol else None,
        })
    h, bh = strategy.get("history"), baseline.get("history")
    if h and bh:
        delta = h["bad_year_net_per_acre"] - bh["bad_year_net_per_acre"]
        out.append({
            "metric": "bad_year_net_per_acre", "label": "Net return in a bad year (1 in 5)", "unit": "$/ac/yr", "dimension": "income",
            "meaning": "Mean minus the swing from 2001-2024 weather replayed through the rotation and from price volatility.",
            "baseline": bh["bad_year_net_per_acre"], "value": h["bad_year_net_per_acre"], "delta": round(delta, 0),
            "delta_pct": None, "direction": _direction(delta, True, 10), "confidence": confidence["income"]["label"], "range": None,
        })
        dv = (h["variability_ratio"] - bh["variability_ratio"]) * 100
        out.append({
            "metric": "income_variability", "label": "Income swing (share of revenue)", "unit": "%", "dimension": "income",
            "meaning": "Year-to-year standard deviation of net return divided by gross revenue. Lower is steadier.",
            "baseline": round(bh["variability_ratio"] * 100, 0), "value": round(h["variability_ratio"] * 100, 0), "delta": round(dv, 0),
            "delta_pct": None, "direction": _direction(dv, False, 1.0), "confidence": confidence["income"]["label"], "range": None,
        })
    return out


def _sentence(b: dict) -> str:
    arrow = "down" if b["delta"] < 0 else "up"
    return f"{b['label']} {arrow} from {_fmt(b['baseline'], b['unit'])} to {_fmt(b['value'], b['unit'])}"


def why_suggested(ctx: FieldContext, strategy: dict, baseline: dict, priorities: dict, insights: dict, bens: list[dict]) -> list[dict]:
    """Reasons, each tagged with what drove it: a priority, the climate record, the soil, or the market."""
    sig = insights["signals"]
    crops = crops_by_id()
    reasons: list[dict] = []
    if strategy["role"] == "baseline":
        reasons.append({"driver": "reference", "text": "This is what the field does today. Every alternative is measured against it with the same models, so the comparison is like for like."})
        strong = [d for d in DIMENSIONS if strategy["scores"][d] >= 60]
        weak = sorted((d for d in DIMENSIONS if strategy["scores"][d] < 45), key=lambda d: strategy["scores"][d])
        if strong:
            reasons.append({"driver": "strength", "text": "Where it holds up: " + "; ".join(DIMENSION_LABELS[d].lower() for d in strong) + "."})
        if weak:
            reasons.append({"driver": "strain", "text": "Where the data shows strain: " + "; ".join(DIMENSION_LABELS[d].lower() for d in weak) + "."})
        reasons.append({"driver": "reference", "text": "Staying with it is a legitimate choice. It needs no new equipment, markets or learning, and its risks are ones you already know."})
        return reasons

    top = sorted(DIMENSIONS, key=lambda d: -float(priorities.get(d, 5)))[:2]
    gains = {d: strategy["scores"][d] - baseline["scores"][d] for d in DIMENSIONS}
    for d in top:
        if gains[d] >= 3:
            best = next((b for b in bens if b["dimension"] == d and b["direction"] == "better"), None)
            reasons.append({"driver": "priority", "dimension": d,
                            "text": f"You ranked \"{DIMENSION_LABELS[d].lower()}\" highly, and this rotation scores {gains[d]:+.0f} points on it against today"
                                    + (f" ({_sentence(best)})." if best else ".")})
    best_other = max((d for d in DIMENSIONS if d not in top), key=lambda d: gains[d])
    if gains[best_other] >= 8:
        reasons.append({"driver": "co-benefit", "dimension": best_other,
                        "text": f"It also improves \"{DIMENSION_LABELS[best_other].lower()}\" by {gains[best_other]:+.0f} points, which you did not rank first."})

    phases = strategy["phases"]
    names = {p["crop_id"] for p in phases}
    new = [c for c in strategy["fit"]["change"]["new_crops"]]
    if ctx.irrigated and sig.get("groundwater_trend_cm_yr") is not None and sig["groundwater_trend_cm_yr"] < -0.3:
        saved = baseline["metrics"]["irrigation_mm_yr"] - strategy["metrics"]["irrigation_mm_yr"]
        if saved > 15:
            reasons.append({"driver": "climate", "text": f"GRACE satellites show regional water storage falling {abs(sig['groundwater_trend_cm_yr']):.1f} cm a year. This rotation pumps {saved:.0f} mm ({saved / 25.4:.1f} in) less each year."})
    if sig["heat_days_35"] >= 12 and any(crops[c]["heat_tmax_c"] >= 37 for c in new):
        tough = [crops[c]["name"] for c in new if crops[c]["heat_tmax_c"] >= 37]
        reasons.append({"driver": "climate", "text": f"NASA POWER counts {sig['heat_days_35']:.0f} days a year above 35 C here"
                        + (", and the count is rising" if sig["heat_trend_per_decade"] > 0.5 else "") + f". {', '.join(tough)} tolerate that heat better than the crops they replace."})
    cool = [crops[c]["name"] for c in new if crops[c]["cycle"] == "winter" or crops[c]["t_plant_c"] < 9]
    if cool and sig["summer_deficit_mm"] > 250:
        reasons.append({"driver": "climate", "text": f"Summer demand outruns rain by {sig['summer_deficit_mm']:.0f} mm. {', '.join(cool)} grow in the cool season and finish before the worst of it."})
    covers = [p for p in phases if p["kind"] == "cover" and (p["biomass_frac"] or 0) >= 0.2]
    if covers:
        base_bare = baseline["metrics"]["bare_months_per_year"]
        reasons.append({"driver": "soil", "text": f"The field is bare {base_bare:.1f} months a year now, and {sig['storm_share']:.0%} of erosive rain falls in {month_range(sig['storm_months'])}. "
                        f"Cover crops ({', '.join(sorted({p['crop_name'] for p in covers}))}) cut bare time to {strategy['metrics']['bare_months_per_year']:.1f} months."})
    legumes = sorted({crops[c]["name"] for c in names if crops[c]["legume"]} - {crops[c]["name"] for y in baseline["years"] for c in y if crops[c]["legume"]})
    if legumes:
        reasons.append({"driver": "soil", "text": f"{', '.join(legumes)} fix nitrogen from the air: purchased nitrogen drops from {baseline['metrics']['n_fertilizer_kg_ha_yr']:.0f} to {strategy['metrics']['n_fertilizer_kg_ha_yr']:.0f} kg/ha a year."})
    om = float(ctx.soil.get("organic_matter_pct") or 0)
    if om and om < 2.0 and strategy["metrics"]["soc_change_t_ha_yr"] > baseline["metrics"]["soc_change_t_ha_yr"] + 0.05:
        reasons.append({"driver": "soil", "text": f"The soil survey puts organic matter at {om:.1f}%, which is low. This rotation returns {strategy['metrics']['carbon_input_t_ha_yr']:.1f} t/ha of carbon a year against {baseline['metrics']['carbon_input_t_ha_yr']:.1f} now."})
    deep = [crops[c]["name"] for c in new if crops[c]["deep_rooted"]]
    if deep:
        reasons.append({"driver": "soil", "text": f"{', '.join(deep)} root below 1.6 m, reaching water and nitrogen that shallower crops leave behind and opening channels for infiltration."})
    if strategy["pests"]["distinct_cash_crops"] > baseline["pests"]["distinct_cash_crops"]:
        short = baseline["pests"]["short_breaks"]
        pest = f" The current rotation returns {short[0]['crop_name'].lower()} every {short[0]['interval_years']} year(s), which favours {', '.join(short[0]['named_pests'][:2]) or 'its specialist pests'}." if short else ""
        reasons.append({"driver": "pest", "text": f"It grows {strategy['pests']['distinct_cash_crops']} different cash crops instead of {baseline['pests']['distinct_cash_crops']}.{pest}"})
    if strategy["tillage"] != baseline["tillage"]:
        reasons.append({"driver": "soil", "text": f"{strategy['tillage_label']} leaves residue on the surface: soil loss changes from {baseline['metrics']['soil_loss_tons_ac_yr']:.1f} to {strategy['metrics']['soil_loss_tons_ac_yr']:.1f} tons/acre a year."})
    verified = [r for r in strategy["market"]["rows"] if r["verified_locally"] and r["access"] >= 0.8 and r["crop_id"] in new]
    if verified:
        reasons.append({"driver": "market", "text": "Local outlets exist for the new crops: " + " ".join(f"{r['crop_name']}: {r['note']}" for r in verified[:2])})
    if not reasons:
        reasons.append({"driver": "priority", "text": "It has the best overall balance across your five priorities among the options that fit this field's season, soil and equipment."})
    return reasons


def evidence(ctx: FieldContext, strategy: dict, baseline: dict, insights: dict, calendar: dict) -> list[dict]:
    """Observed facts (satellite, soil survey) plus the model results that bear on this strategy."""
    gains = {d: abs(strategy["scores"][d] - baseline["scores"][d]) for d in DIMENSIONS}
    wanted = set(sorted(DIMENSIONS, key=lambda d: -gains[d])[:3]) if strategy["role"] != "baseline" else set(DIMENSIONS)
    items = []
    for f in insights["facts"]:
        if f["dimension"] in wanted or f["id"] in ("soil_profile", "crop_history", "rain_total"):
            items.append({"kind": "observed", "id": f["id"], "source": f["source"], "dataset": f["dataset"], "access": f["access"],
                          "statement": f["headline"], "detail": f["detail"], "value": f["value"], "unit": f["unit"], "dimension": f["dimension"]})
    m = strategy["metrics"]
    summ = calendar["summary"]
    model = [
        ("cover_calendar", "erosion", summ["headline"], f"Mean ground cover {m['mean_ground_cover_pct']:.0f}%; modelled soil loss {m['soil_loss_tons_ac_yr']:.1f} tons/acre a year, "
         f"{m['soil_loss_vs_tolerable']:.1f} times the tolerable rate.", "Crop calendar from NASA POWER growing degree days + RUSLE"),
        ("water_budget", "water",
         f"Uses {m['crop_water_use_mm_yr']:.0f} mm of water a year; {m['productive_water_pct']:.0f}% of rain and irrigation goes through the crop",
         (f"Irrigation {m['irrigation_mm_yr']:.0f} mm a year ({m['allocation_used_pct']:.0f}% of the allocation). " if m["allocation_used_pct"] is not None else "")
         + f"Runoff {m['runoff_mm_yr']:.0f} mm, deep drainage {m['deep_drainage_mm_yr']:.0f} mm, unmet crop demand {m['water_stress_pct']:.0f}%.",
         "Monthly FAO-56 soil-water balance on fused rainfall and SSURGO water-holding capacity"),
        ("carbon", "soil", f"Returns {m['carbon_input_t_ha_yr']:.1f} t/ha of carbon a year; soil carbon trend {m['soc_change_t_ha_yr']:+.2f} t/ha a year",
         f"Living roots {m['living_root_months_per_year']:.1f} months a year. Legume and cover-crop nitrogen credit {m['n_legume_credit_kg_ha_yr']:.0f} kg/ha a year.",
         "One-pool soil carbon balance driven by residue, roots, temperature and tillage"),
    ]
    h = strategy.get("history")
    if h:
        model.append(("history", "income", f"Replaying 2001-2024 weather: ${h['mean_net_per_acre']:,.0f}/acre on average, ${h['bad_year_net_per_acre']:,.0f} in a bad year",
                      f"Worst years: {', '.join(map(str, h['worst_years']))}. Weather alone moves net return by ${h['weather_sd_per_acre']:,.0f}/acre (one standard deviation).",
                      "24 years of NASA POWER weather run through the rotation, every phase in every year"))
    for mid, dim, statement, detail, method in model:
        if dim in wanted or strategy["role"] == "baseline":
            items.append({"kind": "modelled", "id": mid, "source": "FieldShift model", "dataset": method, "access": "model",
                          "statement": statement, "detail": detail, "value": None, "unit": None, "dimension": dim})
    return items


STANDING_GAPS = [
    ("compaction", "Compaction and hardpans below the surface",
     "No satellite sees a plough pan. The model assumes roots can use the full soil-survey depth; a compacted layer would cut water storage and the benefit of deep-rooted crops.",
     "Push a penetrometer or dig a pit in spring when the soil is moist."),
    ("biology", "Soil life, nematodes and disease inoculum",
     "Nematode counts, disease carry-over and microbial activity are invisible from orbit. Pest scores use rotation rules of thumb, not what is in this soil.",
     "Pull nematode and soil-health samples; review the field's disease history."),
    ("drainage", "Tile lines, drainage and irrigation hardware",
     "Tile spacing, outlet condition, well capacity and system uniformity are not in any public dataset. One on/off setting stands in for them.",
     "Check tile maps, well test records and a recent irrigation uniformity test."),
    ("genetics", "Varieties, hybrids and maturity groups",
     "Each crop is a single mid-range type. Variety choice can move maturity by weeks and drought or disease tolerance by a lot.",
     "Match maturity and disease packages to the planting windows shown, with your seed adviser."),
    ("contracts", "Contracts, basis, leases and programme rules",
     "Prices are multi-year averages. Forward contracts, local basis, landlord terms, crop insurance and conservation-programme payments can outweigh every number here.",
     "Price each crop with your buyer, lender and insurance agent before committing acres."),
    ("within_field", "Variation inside the field",
     "Weather inputs are 10-55 km pixels and the soil is one dominant map-unit component. Knolls, draws, sandy streaks and saline spots are averaged away.",
     "Overlay yield maps or walk the field; consider zoning the rotation."),
]


def gaps(ctx: FieldContext, strategy: dict, layers: list[dict], confidence: dict, ndvi_check: dict | None) -> dict:
    """What the tool cannot know, how sure it is, and what would close each gap."""
    crops = crops_by_id()
    items = []
    for row in layers:
        if row["access"] == "unavailable":
            items.append({"id": f"layer_{row['id']}", "kind": "data", "severity": "medium", "topic": f"{row['label']}: not available",
                          "detail": row.get("note") or "This layer could not be retrieved.", "close_by": "Supply a local measurement or retry when the service is back."})
        elif row["access"] == "proxy":
            items.append({"id": f"layer_{row['id']}", "kind": "data", "severity": "medium", "topic": f"{row['label']}: a stand-in product was used",
                          "detail": row.get("note") or "", "close_by": "Add a NASA Earthdata login to pull the native product, or check against a field sensor."})
        elif row["representativeness"] < 0.5 and row["id"] in ("soil_moisture", "power_precip", "lst", "grace"):
            ratio = row["pixel_to_field_ratio"]
            items.append({"id": f"scale_{row['id']}", "kind": "resolution", "severity": "low",
                          "topic": f"{row['label']}: one pixel is {ratio:.0f}x the width of this field" if ratio else f"{row['label']}: coarse",
                          "detail": f"Native resolution {row['native_resolution_m'] / 1000:.0f} km. {row['harmonisation']}",
                          "close_by": "A rain gauge, soil-moisture probe or well record on the farm beats any pixel this size."})
    if ctx.soil.get("generic"):
        items.append({"id": "soil_generic", "kind": "data", "severity": "high", "topic": "No soil survey data for this field",
                      "detail": ("The USDA soil survey did not answer in time or does not cover this location, so a generic loam was assumed. "
                                 "Water-holding capacity, erodibility and organic matter drive most results."),
                      "close_by": "Reload the field in a minute (U.S. locations), or use a soil test or national soil-map values."})
    no_yield = sorted({p["crop_name"] for p in strategy["economics"] if p["kind"] != "cover" and not p.get("local_reference", True)})
    if no_yield:
        items.append({"id": "yield_reference", "kind": "data", "severity": "medium", "topic": "No local yield history for " + ", ".join(no_yield),
                      "detail": "National typical yields were used, then adjusted for this field's water, heat and soil.", "close_by": "Ask Extension for variety-trial yields in your county."})
    unverified = [r["crop_name"] for r in strategy["market"]["rows"] if not r["verified_locally"]]
    if unverified:
        items.append({"id": "market_unverified", "kind": "data", "severity": "medium", "topic": "Local buyers not confirmed for " + ", ".join(sorted(set(unverified))),
                      "detail": "A default market-access score was used.", "close_by": "Call the nearest elevators, processors or feed users."})
    weak_covers = [p for p in strategy["phases"] if p["kind"] in ("cover", "forage") and p["biomass_frac"] is not None and p["biomass_frac"] < 0.45]
    if weak_covers:
        items.append({"id": "cover_establishment", "kind": "model", "severity": "medium",
                      "topic": "Cover-crop growth is uncertain: " + ", ".join(sorted({p['crop_name'] for p in weak_covers})),
                      "detail": "The window between crops gives it under half of its potential growth in a normal year; a dry or cold autumn gives less.",
                      "close_by": "Try a strip first, seed earlier (interseed or fly on), or pick a faster species."})
    if ndvi_check and strategy["role"] == "baseline":
        sev = {"strong": "low", "fair": "low", "weak": "high"}[ndvi_check["agreement"]]
        items.append({"id": "calendar_check", "kind": "validation", "severity": sev, "topic": f"Satellite check of the assumed crop calendar: {ndvi_check['agreement']} agreement",
                      "detail": ndvi_check["explanation"], "close_by": "Edit the baseline rotation and planting dates to match your records."})
    if any(crops[p["crop_id"]]["cycle"] == "perennial" for p in strategy["phases"]):
        items.append({"id": "perennial_model", "kind": "model", "severity": "medium", "topic": "Hay yields by cutting are not modelled",
                      "detail": "Alfalfa is treated as one seasonal total; stand decline, cutting schedule and hay quality are not represented.", "close_by": "Use local hay budgets."})
    for gid, topic, detail, close in STANDING_GAPS:
        items.append({"id": gid, "kind": "blind_spot", "severity": "standing", "topic": topic, "detail": detail, "close_by": close})

    spread = {d: round((1 - confidence[d]["combined"]) * 22, 0) for d in DIMENSIONS}
    return {
        "items": items,
        "confidence": {d: confidence[d] for d in DIMENSIONS},
        "overall_confidence": confidence["overall"],
        "score_uncertainty": spread,
        "statement": ("Scores are planning estimates from a monthly model. Treat a difference of fewer points than the uncertainty shown for "
                      "that dimension as a tie, and treat every dollar figure as a ranking aid, not a budget."),
    }


def risks(ctx: FieldContext, strategy: dict, baseline: dict, insights: dict) -> list[dict]:
    """Checklist for the farmer and local advisers. Each item says who should review it and why it applies here."""
    crops = crops_by_id()
    sig = insights["signals"]
    out: list[dict] = []
    m = strategy["metrics"]

    seen: set[str] = set()

    def add(rid: str, category: str, title: str, detail: str, who: list[str], severity: str = "check") -> None:
        if rid in seen:  # a crop grown twice in the rotation raises its checks once
            return
        seen.add(rid)
        out.append({"id": rid, "category": category, "title": title, "detail": detail, "who": who, "severity": severity})

    if strategy["role"] == "baseline":
        if m["soil_loss_vs_tolerable"] > 1.0:
            add("erosion_over_t", "Soil", "Soil loss is above the tolerable rate",
                f"Modelled loss is {m['soil_loss_vs_tolerable']:.1f} times what the soil survey says this soil can sustain. Staying the course means continued topsoil loss.", [WHO_NRCS, WHO_FARMER], "caution")
        for s in strategy["pests"]["short_breaks"][:2]:
            add(f"resistance_{s['crop_id']}", "Pests", f"{s['crop_name']} returns every {s['interval_years']} year(s)",
                f"Recommended gap is {s['recommended_years']} years. Watch for {', '.join(s['named_pests']) or 'specialist pests'} and for herbicide-resistant weeds selected by repeating the same programme.", [WHO_CCA], "caution")
        if ctx.irrigated and sig.get("groundwater_trend_cm_yr") is not None and sig["groundwater_trend_cm_yr"] < -0.3:
            add("water_supply", "Water", "The water supply this rotation depends on is declining",
                f"The rotation uses {m['allocation_used_pct']:.0f}% of the allocation in a normal year. Ask how well yield and allocation are expected to change over the next ten years.", [WHO_WATER, WHO_FARMER], "caution")
        if m["bare_months_per_year"] >= 4:
            add("bare_soil", "Soil", f"Soil is bare {m['bare_months_per_year']:.0f} months a year",
                "Bare months coincide with part of the erosive-rain season. Residue management alone can change this without changing crops.", [WHO_NRCS, WHO_FARMER])
        add("status_quo", "Business", "Known risks are still risks", "The current rotation's familiarity hides its exposure to one or two markets and one or two pest complexes.", [WHO_FARMER])
        return out

    order = [p for p in strategy["phases"]]
    for i, ph in enumerate(order):
        prev = order[i - 1]
        if ph["crop_id"] in SENSITIVE_FOLLOWERS and prev["crop_id"] in RESIDUAL_HERBICIDE_CROPS and ph["crop_id"] != prev["crop_id"]:
            add(f"carryover_{ph['crop_id']}", "Herbicides", f"Herbicide carryover into {ph['crop_name'].lower()}",
                f"Residual herbicides used in {prev['crop_name'].lower()} (atrazine, HPPD inhibitors, sulfonylureas, imidazolinones) can injure {ph['crop_name'].lower()} for 10-36 months, longer in dry or high-pH soil"
                + (f" (this soil is pH {ctx.soil['ph']})" if float(ctx.soil.get('ph') or 7) >= 7.5 else "") + ". Check every label's rotation interval against your spray records.", [WHO_CCA, WHO_FARMER], "critical")
            break
    covers = [p for p in order if p["kind"] == "cover"]
    if covers:
        dry = sig["aridity_index"] < 0.6 and not ctx.irrigated
        add("cover_termination", "Cover crops", "Cover-crop termination timing",
            ("In a dry region a cover crop left too long uses the moisture the next crop needs. " if dry else "A cover crop terminated late can tie up nitrogen and slow soil warming. ")
            + "Agree a termination date and method (herbicide, roller, tillage, winter-kill) and confirm it meets crop-insurance cover-crop rules for your county.",
            [WHO_EXT, WHO_INSURER, WHO_FARMER], "caution" if dry else "check")
        if any(p["crop_id"] in ("cereal_rye", "cover_mix") for p in covers) and any(o["crop_id"] == "corn" for o in order):
            add("rye_before_corn", "Cover crops", "Cereal rye ahead of corn", "Rye can host seedling diseases and tie up nitrogen for corn. Terminate 10-14 days before planting and consider starter nitrogen.", [WHO_CCA])
        if any(p["winterkills"] for p in covers):
            add("winterkill_timing", "Cover crops", "Winter-killed covers must be seeded early", "Radish and oats need 6-8 weeks of growth before a hard freeze to be worth the seed.", [WHO_FARMER])
    for b in strategy["pests"]["green_bridges"]:
        add(f"bridge_{b['group']}", "Pests", f"{b['cover']} can carry disease into {b['next_crop'].lower()}",
            "The cover crop and the crop after it host some of the same diseases or insects (a 'green bridge'). Leave a host-free gap or choose a different cover.", [WHO_CCA], "caution")
    for s in strategy["pests"]["short_breaks"][:2]:
        add(f"short_break_{s['crop_id']}", "Pests", f"{s['crop_name']} still returns sooner than recommended",
            f"Every {s['interval_years']} year(s) against a recommended {s['recommended_years']}. Scout for {', '.join(s['named_pests']) or 'host-specific pests'}.", [WHO_CCA])
    labels = load_catalog()["equipment_labels"]
    if strategy["equipment_needed"]:
        add("equipment", "Equipment", "Equipment you do not have listed",
            "Needs: " + ", ".join(labels.get(e, e) for e in strategy["equipment_needed"]) + ". "
            + ("Custom operators or rental may cover it; get a quote and a date commitment." if ctx.custom_hire else "No custom hire was indicated, so this is a purchase or a barrier."),
            [WHO_FARMER], "caution")
    for row in strategy["market"]["rows"]:
        if row["crop_id"] in strategy["fit"]["change"]["new_crops"] and (row["access"] < 0.75 or not row["verified_locally"]):
            add(f"buyer_{row['crop_id']}", "Markets", f"Confirm a buyer for {row['crop_name'].lower()}", row["note"] + " Get a price, delivery window and quality specs in writing before buying seed.", [WHO_BUYER, WHO_FARMER], "caution")
    new = strategy["fit"]["change"]["new_crops"]
    if new:
        add("insurance", "Business", "Crop insurance and programme eligibility for new crops",
            f"Check whether {', '.join(crops[c]['name'].lower() for c in new)} are insurable in your county, how a new crop affects your yield history, and any landlord or conservation-contract terms.", [WHO_INSURER, WHO_FARMER])
    if any(len(y) == 0 for y in baseline["years"]) and not any(len(y) == 0 for y in strategy["years"]):
        add("fallow_replacement", "Water", "Replacing fallow uses stored soil water",
            f"The model shows the following crop under {m['water_stress_pct']:.0f}% water stress in a normal year. In a dry autumn the next winter crop may be seeded into dry soil; decide in advance when you would revert to fallow.", [WHO_EXT, WHO_FARMER], "caution")
    if strategy["tillage"] != baseline["tillage"]:
        wet = "poor" in str(ctx.soil.get("drainage_class", "")).lower()
        add("tillage_transition", "Soil", f"Moving to {strategy['tillage_label'].lower()}",
            ("This soil is poorly drained, so residue will keep it colder and wetter in spring; strip-till may fit better. " if wet else "")
            + "Expect a 3-5 year transition: planter set-up for residue, nutrient stratification, and different weed pressure.", [WHO_NRCS, WHO_EXT])
    if m["n_legume_credit_kg_ha_yr"] > baseline["metrics"]["n_legume_credit_kg_ha_yr"] + 10:
        add("n_credit", "Nutrients", "Verify nitrogen credits before cutting fertiliser",
            "Legume credits vary with stand, weather and termination date. Use a pre-sidedress or in-season nitrate test the first years.", [WHO_CCA])
    late = [p for p in order if p["delay_months"]]
    if late:
        add("tight_window", "Timing", "Tight planting windows", "; ".join(f"{p['crop_name']} goes in about {p['delay_months']} month(s) later than ideal" for p in late) + ". A wet harvest or early frost breaks the sequence; have a fallback crop.", [WHO_FARMER])
    if ctx.irrigated and m["allocation_used_pct"] and m["allocation_used_pct"] > 95:
        add("allocation_limit", "Water", "The rotation uses the full water allocation", "Any cut in allocation or well yield becomes crop stress. Check peak-month demand against system capacity.", [WHO_WATER], "caution")
    if float(ctx.soil.get("ec_ds_m") or 0) >= 2.0:
        add("salinity", "Soil", "Salinity", f"Soil EC is {ctx.soil['ec_ds_m']} dS/m. Reduced irrigation can concentrate salts; plan a leaching fraction and test water quality.", [WHO_CCA, WHO_WATER])
    if any(crops[p["crop_id"]]["cycle"] == "perennial" for p in order):
        add("perennial", "Business", "A multi-year stand is a multi-year commitment", "Establishment cost, stand life and hay marketing need their own budget. Do not reseed alfalfa into old alfalfa (autotoxicity).", [WHO_EXT, WHO_FARMER])
    if ctx.livestock and covers:
        add("grazing", "Livestock", "Grazing cover crops", "Check herbicide grazing restrictions, nitrate and prussic-acid risk, fencing and water.", [WHO_EXT])
    add("try_small", "Process", "Try it on part of the field first", "A strip trial for two seasons tests the planting windows, equipment and markets with little at stake.", [WHO_FARMER, WHO_EXT])
    return out


def build_explanation(ctx: FieldContext, strategy: dict, baseline: dict, priorities: dict, insights: dict,
                      layers: list[dict], confidence: dict, calendar: dict, ndvi_check: dict | None) -> dict:
    bens = benefits(strategy, baseline, confidence) if strategy["role"] != "baseline" else []
    better = [b for b in bens if b["direction"] == "better"]
    worse = [b for b in bens if b["direction"] == "worse"]
    return {
        "why": why_suggested(ctx, strategy, baseline, priorities, insights, bens),
        "evidence": evidence(ctx, strategy, baseline, insights, calendar),
        "benefits": {"items": bens, "improves": len(better), "trade_offs": len(worse),
                     "summary": _benefit_summary(strategy, better, worse)},
        "gaps": gaps(ctx, strategy, layers, confidence, ndvi_check),
        "risks": risks(ctx, strategy, baseline, insights),
    }


def _benefit_summary(strategy: dict, better: list[dict], worse: list[dict]) -> str:
    if strategy["role"] == "baseline":
        return "This is the reference. Benefits of the alternatives are measured against it."
    parts = []
    if better:
        parts.append("Improves: " + "; ".join(_sentence(b) for b in better[:3]) + ".")
    if worse:
        parts.append("Costs: " + "; ".join(_sentence(b) for b in worse[:2]) + ".")
    return " ".join(parts) or "No material change against the current rotation."
