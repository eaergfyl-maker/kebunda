"""Crop calendar scheduler: turns "corn, then soybean with a rye cover" into months on the ground.

Planting and harvest dates are not looked up from a regional table. They are derived from
the field's own NASA POWER temperatures with growing degree days (GDD), so the calendar
moves with latitude, with elevation, and with a warming scenario.

A rotation is `years: list[list[crop_id]]`, one inner list per rotation year:
    position 0   the main crop harvested that year (fall-sown crops were planted the autumn before)
    position 1+  what follows it the same year: a double crop, a cover crop, or a relay forage
    []           a fallow year
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.services.rotation_engine.context import Climate
from app.utils.geo import DAYS_IN_MONTH

MAX_SPRING_SEASON_MONTHS = 9


@dataclass
class Phase:
    crop: dict
    year_index: int
    kind: str  # cash | cover | forage | perennial
    plant: int  # absolute month index on the rotation timeline (may be < 0 for fall sowing)
    end: int  # last month occupied (inclusive)
    maturity: int  # month the crop stops growing (end minus dry-down)
    delay_months: int = 0
    biomass_frac: float = 1.0  # covers / forages: share of potential biomass reached
    winterkilled_at: int | None = None
    stand_years: int = 1
    issues: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.crop["id"]


@dataclass
class Schedule:
    n_years: int
    phases: list[Phase]
    feasible: bool
    issues: list[str]
    # per rotation-month arrays (length n_years * 12)
    occupant: list[int | None] = field(default_factory=list)  # index into phases
    canopy: list[float] = field(default_factory=list)  # ground shaded by living or standing crop, 0-1
    green: list[float] = field(default_factory=list)  # transpiring fraction relative to full canopy, 0-1

    @property
    def n_months(self) -> int:
        return self.n_years * 12


def month_gdd(cl: Climate, m: int, t_base: float, cap: float = 30.0) -> float:
    tx, tn = min(cl.tmax[m % 12], cap), max(cl.tmin[m % 12], t_base)
    return max(0.0, (tx + tn) / 2.0 - t_base) * DAYS_IN_MONTH[m % 12]


def _season_start(cl: Climate) -> int:
    """Calendar month that opens the growing year (January north of the equator, July south)."""
    return 0 if cl.lat >= 0 else 6


def spring_plant_month(cl: Climate, crop: dict) -> int | None:
    start = _season_start(cl)
    for k in range(12):
        m = (start + k) % 12
        if cl.tmean[m] >= crop["t_plant_c"] and cl.tmin[m] > -1.0:
            return start + k
    return None


def fall_plant_offset(cl: Climate, crop: dict, slack: float = 0.0) -> int:
    """Months after the season start (Aug..Dec in the north) when it is cool enough to sow a fall crop."""
    start = _season_start(cl)
    for k in range(7, 12):
        if cl.tmean[(start + k) % 12] <= crop["t_plant_c"] + slack:
            return k
    return 11


def _grow(cl: Climate, crop: dict, plant: int, target: float, limit: int) -> tuple[int | None, float]:
    """Accumulate GDD from `plant` until `target`. Returns (maturity month, GDD reached).

    Spring-sown crops are frost-tender: running into a freezing month before maturity fails.
    """
    total = 0.0
    tender = crop["cycle"] == "spring"
    for m in range(plant, plant + limit + 1):
        if tender and m > plant and cl.tmin[m % 12] < -1.0:
            return None, total
        total += month_gdd(cl, m, crop["t_base_c"]) * (0.5 if m == plant else 1.0)
        # heat units alone would rush photoperiod-sensitive crops in hot climates, so each
        # crop also has a minimum season length
        if total >= target and m - plant + 1 >= crop.get("min_season_months", 0):
            return m, total
    return None, total


def build_schedule(years: list[list[str]], crops: dict[str, dict], cl: Climate) -> Schedule:
    n = len(years)
    issues: list[str] = []
    feasible = True
    start = _season_start(cl)
    coldest_tmin = min(cl.tmin)

    # ---- pass A: main and double crops (anything harvested for sale) --------------------
    mains: list[Phase] = []
    y = 0
    while y < n:
        entries = years[y]
        for pos, cid in enumerate(entries):
            crop = crops[cid]
            if crop["role"] == "cover" or (pos > 0 and crop["cycle"] == "winter"):
                continue  # placed in pass B
            base = y * 12
            if crop["cycle"] == "perennial":
                span = 1
                while y + span < n and years[y + span][:1] == [cid]:
                    span += 1
                if span == n:  # the whole rotation is one continuous stand
                    mains.append(Phase(crop, y, "perennial", 0, n * 12 - 1, n * 12 - 1, stand_years=n))
                else:
                    pm = spring_plant_month(cl, crop) or 3
                    mains.append(Phase(crop, y, "perennial", base + pm, base + span * 12 - 2, base + span * 12 - 2, stand_years=span))
                y += span - 1
                break
            if crop["cycle"] == "winter":
                plant = base - 12 + fall_plant_offset(cl, crop)
                if crop.get("min_winter_tmin_c") is not None and coldest_tmin < crop["min_winter_tmin_c"]:
                    feasible = False
                    issues.append(f"{crop['name']} is unlikely to survive winter here (coldest month averages {coldest_tmin:.0f} C at night).")
                maturity, _ = _grow(cl, crop, plant, crop["gdd_to_maturity"], 13)
                if maturity is None:
                    feasible = False
                    issues.append(f"{crop['name']} does not accumulate enough warmth to mature.")
                    maturity = plant + 10
                mains.append(Phase(crop, y, "forage" if crop["role"] == "forage" else "cash", plant, maturity + crop["dry_down_months"], maturity))
            else:
                pm = spring_plant_month(cl, crop)
                if pm is None:
                    feasible = False
                    issues.append(f"It never gets warm enough to plant {crop['name']}.")
                    pm = 4
                plant = base + pm
                maturity, _ = _grow(cl, crop, plant, crop["gdd_to_maturity"], MAX_SPRING_SEASON_MONTHS)
                if maturity is None:
                    feasible = False
                    issues.append(f"The season is too short or cool for {crop['name']} to mature.")
                    maturity = plant + 5
                mains.append(Phase(crop, y, "cash", plant, maturity + crop["dry_down_months"], maturity))
        y += 1

    mains.sort(key=lambda p: p.plant)
    # resolve overlaps in time order; two sweeps so the wrap-around (last crop -> first crop) settles
    for sweep in range(2):
        for i, ph in enumerate(mains):
            if ph.kind == "perennial" and ph.stand_years == n:
                continue
            prev = mains[i - 1]
            prev_end = prev.end - (n * 12 if i == 0 else 0)
            if i == 0 and sweep == 0 and len(mains) > 1:
                continue
            if len(mains) == 1:
                prev_end = ph.end - n * 12
            if ph.plant <= prev_end:
                delay = prev_end + 1 - ph.plant
                ph.plant += delay
                ph.delay_months += delay
                crop = ph.crop
                if ph.kind == "perennial":
                    continue
                limit = 13 if crop["cycle"] == "winter" else MAX_SPRING_SEASON_MONTHS
                maturity, _ = _grow(cl, crop, ph.plant, crop["gdd_to_maturity"], limit)
                too_cold = crop["cycle"] == "winter" and cl.tmean[ph.plant % 12] < 3.0
                if maturity is None or too_cold or ph.delay_months > (2 if crop["cycle"] == "winter" else 3):
                    feasible = False
                    issues.append(f"{crop['name']} cannot be planted in time after {prev.crop['name']} comes off.")
                    maturity = maturity or ph.plant + 5
                ph.maturity, ph.end = maturity, maturity + crop["dry_down_months"]
    for ph in mains:
        if ph.delay_months and not any(ph.crop["name"] in s for s in issues):
            ph.issues.append(f"Planted about {ph.delay_months} month(s) later than ideal because the previous crop is still in the field.")

    # ---- pass B: cover crops and relay forages fill the gaps -----------------------------
    covers: list[Phase] = []
    for y, entries in enumerate(years):
        for pos, cid in enumerate(entries):
            crop = crops[cid]
            if not (crop["role"] == "cover" or (pos > 0 and crop["cycle"] == "winter")):
                continue
            base = y * 12
            # mains of this year and earlier come before the cover; next year's mains end its window
            ext = [(p.year_index + k * n, p.plant + k * n * 12, p.end + k * n * 12) for p in mains for k in (-1, 0, 1)]
            prev_end = max((e for yi, _pl, e in ext if yi <= y), default=base + start - 1)
            next_plant = min((pl for yi, pl, _e in ext if yi > y and pl > prev_end), default=prev_end + 9)
            if crop["cycle"] == "winter":
                plant = max(prev_end + 1, base + fall_plant_offset(cl, crop, slack=4.0))
            else:
                plant = prev_end + 1
            end = next_plant - 1
            ph = Phase(crop, y, "forage" if crop["role"] == "forage" else "cover", plant, end, end)
            if end < plant:
                ph.biomass_frac = 0.0
                ph.end = ph.maturity = plant
                ph.issues.append(f"No open window for {crop['name']} before the next crop is planted.")
                covers.append(ph)
                continue
            target = crop["gdd_to_maturity"]  # potential biomass is reached at maturity
            gdd = month_gdd(cl, prev_end, crop["t_base_c"]) * 0.25  # seeded into or right behind the previous crop
            for m in range(plant, end + 1):
                if crop["cycle"] == "spring" and cl.tmean[m % 12] < crop["t_base_c"] + 2:
                    ph.end = ph.maturity = max(plant, m - 1)
                    break
                if crop.get("winterkill") and cl.tmin[m % 12] < -4.0 and ph.winterkilled_at is None:
                    ph.winterkilled_at = m
                    break
                gdd += month_gdd(cl, m, crop["t_base_c"])
                if gdd >= target:
                    ph.end = ph.maturity = m  # forage is cut; a cover that sets seed is terminated
                    break
            hardy = crop.get("min_winter_tmin_c")
            if hardy is not None and not crop.get("winterkill") and coldest_tmin < hardy:
                ph.issues.append(f"{crop['name']} often winter-kills here; expect a thin stand in cold years.")
                gdd *= 0.4
            months = range(plant, ph.end + 1)
            p_sum = sum(cl.precip[m % 12] for m in months)
            e_sum = sum(cl.et0[m % 12] for m in months) or 1.0
            moisture = max(0.25, min(1.0, p_sum / (0.5 * e_sum)))
            ph.biomass_frac = round(max(0.0, min(1.0, gdd / target)) * moisture, 3)
            if ph.biomass_frac < 0.2:
                ph.issues.append(f"{crop['name']} has too short or too dry a window to establish well ({ph.biomass_frac:.0%} of potential growth).")
            covers.append(ph)

    phases = sorted(mains + covers, key=lambda p: p.plant)
    sched = Schedule(n_years=n, phases=phases, feasible=feasible, issues=issues)
    _paint(sched, cl)
    return sched


def _paint(s: Schedule, cl: Climate) -> None:
    """Fill the month-by-month occupant / canopy / green arrays."""
    nm = s.n_months
    s.occupant, s.canopy, s.green = [None] * nm, [0.0] * nm, [0.0] * nm
    for idx, ph in enumerate(s.phases):
        crop, cmax = ph.crop, ph.crop["canopy_max"]
        if ph.kind == "perennial":
            for k, m in enumerate(range(ph.plant, ph.end + 1)):
                establish = min(1.0, (k + 1) / 3.0) if ph.stand_years < s.n_years else 1.0
                active = cl.tmean[m % 12] > crop["t_base_c"]
                s.occupant[m % nm] = idx
                s.canopy[m % nm] = cmax * establish * (1.0 if active else 0.55)
                s.green[m % nm] = establish * (0.9 if active else 0.1)  # hay cuts keep average cover below full
            continue
        if ph.biomass_frac <= 0 and ph.kind != "cash":
            continue
        grow_end = ph.winterkilled_at if ph.winterkilled_at is not None else ph.maturity
        total = sum(month_gdd(cl, m, crop["t_base_c"]) * (0.5 if m == ph.plant else 1.0) for m in range(ph.plant, grow_end + 1)) or 1.0
        acc = 0.0
        for m in range(ph.plant, ph.end + 1):
            if s.occupant[m % nm] is not None and s.phases[s.occupant[m % nm]].kind in ("cash", "perennial") and ph.kind in ("cover", "forage"):
                continue
            s.occupant[m % nm] = idx
            if ph.winterkilled_at is not None and m >= ph.winterkilled_at:
                s.canopy[m % nm], s.green[m % nm] = 0.0, 0.0  # dead mulch is tracked as residue
                continue
            if m > ph.maturity:  # dry-down: standing but no longer transpiring
                s.canopy[m % nm], s.green[m % nm] = cmax * 0.6, 0.0
                continue
            step = month_gdd(cl, m, crop["t_base_c"]) * (0.5 if m == ph.plant else 1.0)
            f = (acc + step / 2.0) / total
            acc += step
            if ph.kind == "cash":
                ramp = min(1.0, f / 0.4)
                cover = ramp if f <= 0.8 else 1.0 - 0.4 * (f - 0.8) / 0.2
                green = ramp if f <= 0.8 else 1.0 - 0.8 * (f - 0.8) / 0.2
            else:
                scale = 1.0 - math.exp(-3.0 * ph.biomass_frac)  # a thin stand still shades a lot of ground
                cover = green = min(1.0, f / 0.5) * scale
            s.canopy[m % nm], s.green[m % nm] = cmax * cover, green


def describe(s: Schedule) -> list[dict]:
    """Serializable phase list for the timeline UI."""
    out = []
    nm = s.n_months
    for ph in s.phases:
        out.append({
            "crop_id": ph.id, "crop_name": ph.crop["name"], "kind": ph.kind, "year_index": ph.year_index,
            "plant_month": ph.plant % nm, "end_month": ph.end % nm,
            "plant_calendar_month": ph.plant % 12, "end_calendar_month": ph.end % 12,
            "duration_months": ph.end - ph.plant + 1, "wraps": (ph.plant % nm) > (ph.end % nm),
            "delay_months": ph.delay_months,
            "biomass_frac": ph.biomass_frac if ph.kind in ("cover", "forage") else None,
            "winterkills": ph.winterkilled_at is not None, "issues": ph.issues,
        })
    return out
