"""Fusion, crop calendar and field simulation: physical sanity and agronomic direction."""
from __future__ import annotations

import pytest

from app.services import analysis
from app.services.fusion_engine import climate, harmonize
from app.services.rotation_engine.context import crops_by_id, rainfall_erosivity
from app.services.rotation_engine.schedule import build_schedule
from app.services.rotation_engine.simulate import expected_runoff_per_wet_day, simulate
from app.utils import geo, stats

# ----------------------------------------------------------------------------- fusion


def test_saxton_rawls_orders_soil_water_states():
    for sand, clay, om in [(40, 20, 2.5), (10, 30, 4.0), (85, 5, 1.0), (20, 50, 2.0)]:
        h = harmonize.saxton_rawls(sand, clay, om)
        assert 0 < h["wilting_point"] < h["field_capacity"] < h["saturation"] < 0.7
    assert harmonize.saxton_rawls(85, 5, 1)["available_water"] < harmonize.saxton_rawls(20, 20, 3)["available_water"]


def test_precip_fusion_weights_follow_measured_error():
    comparison = {
        "monthly_normals": {"merra2": [60.0] * 12, "imerg": [52.0] * 12, "ground": [50.0] * 12},
        "vs_ground": {"merra2": {"rmse_mm_month": 25.0}, "imerg": {"rmse_mm_month": 8.0}},
    }
    f = harmonize.fuse_precip(comparison)
    assert sum(f["weights"].values()) == pytest.approx(1.0, abs=0.02)
    assert f["weights"]["ground"] > f["weights"]["imerg"] > f["weights"]["merra2"]
    assert 50.0 <= f["monthly_mm"][0] <= 53.0  # pulled to the gauges, not the plain average
    assert all(0.5 <= b <= 1.0 for b in f["bias_vs_merra2"])


def test_precip_fusion_without_ground_reference_still_works():
    f = harmonize.fuse_precip({"monthly_normals": {"merra2": [40.0] * 12, "imerg": [60.0] * 12, "ground": None}, "vs_ground": None})
    assert not f["has_ground"] and 40 < f["monthly_mm"][0] < 60
    assert f["relative_sigma"][0] > 0.15  # disagreement between sources widens the band


def test_layer_inventory_scores_resolution_gap(iowa):
    b, _ = iowa
    rows = {r["id"]: r for r in b["layers"]}
    assert all(0.0 <= r["confidence"] <= 1.0 for r in rows.values())
    # a 55 km soil-moisture cell says less about one field than a 30 m soil survey polygon
    assert rows["soil_moisture"]["representativeness"] < rows["ssurgo"]["representativeness"]
    assert rows["soil_moisture"]["pixel_to_field_ratio"] > 10
    assert rows["grace"]["representativeness"] < 0.5
    conf = b["confidence"]
    assert set(conf) >= {"water", "soil", "erosion", "pest", "income", "overall"}
    assert conf["water"]["label"] in {"high", "moderate", "low"}


def test_daily_record_is_harmonised_to_months():
    dates, tmax, tmin, pr = [], [], [], []
    for year in (2020, 2021):
        for month in range(1, 13):
            for day in range(1, 29):
                dates.append(f"{year}{month:02d}{day:02d}")
                warm = 5 <= month <= 9
                tmax.append(30.0 if warm else 2.0)
                tmin.append(15.0 if warm else -6.0)
                pr.append(20.0 if (warm and day % 7 == 0) else 0.0)
    series = {k: [0.5] * len(dates) for k in ("wet_root", "wet_top", "solar", "rh", "wind", "tskin")}
    series.update(tmax=tmax, tmin=tmin, precip=pr, precip_imerg=pr)
    s = climate.summarise_daily({"dates": dates, "series": series}, 42.0)
    assert s["years"] == [2020, 2021]
    assert s["monthly"]["frost_days"][0] > 25 and s["monthly"]["frost_days"][6] == 0
    assert s["monthly"]["erosive_days"][6] == pytest.approx(4 * 31 / 28, abs=0.2)
    assert sum(s["monthly"]["erosivity_share"]) == pytest.approx(1.0, abs=0.01)
    assert s["monthly"]["et0"][6] > s["monthly"]["et0"][0] > 0
    assert 100 < s["frost"]["frost_free_days_median"] < 200


# ------------------------------------------------------------------------- small physics


def test_reference_et_responds_to_heat_and_latitude():
    assert geo.hargreaves_et0_mm_day(40, 197, 34, 18) > geo.hargreaves_et0_mm_day(40, 197, 30, 18) > 0
    assert geo.hargreaves_et0_mm_day(40, 15, 5, -5) < 2.0


def test_ls_factor_rises_with_slope_and_length():
    assert geo.ls_factor(8, 100) > geo.ls_factor(2, 100) > geo.ls_factor(2, 30) > 0


def test_expected_runoff_is_monotonic():
    assert expected_runoff_per_wet_day(10, 90) > expected_runoff_per_wet_day(10, 70) >= 0
    # same curve number, bigger storms: more than proportionally more runoff
    assert expected_runoff_per_wet_day(20, 80) > 2 * expected_runoff_per_wet_day(10, 80)
    assert expected_runoff_per_wet_day(10, 80) < 10


def test_erosivity_methods():
    assert rainfall_erosivity(900) > rainfall_erosivity(450) > 0
    assert rainfall_erosivity(420, "req_nwrr") > rainfall_erosivity(420)  # thawing-soil erosion in the Palouse


def test_theil_sen_finds_a_trend_and_ignores_noise():
    xs = list(range(2001, 2025))
    up = stats.theil_sen(xs, [10 + 0.5 * (x - 2001) for x in xs])
    assert up["slope"] == pytest.approx(0.5) and up["significant"]
    flat = stats.theil_sen(xs, [5, 6] * 12)
    assert abs(flat["slope"]) < 0.1 and not flat["significant"]


# ------------------------------------------------------------------------- crop calendar


def _phase(sched, crop_id):
    return next(p for p in sched.phases if p.id == crop_id)


def test_calendar_comes_from_local_temperatures(iowa, kansas):
    crops = crops_by_id()
    ia = build_schedule([["corn"], ["soybean"]], crops, iowa[1].climate)
    assert ia.feasible
    corn = _phase(ia, "corn")
    assert corn.plant % 12 in (3, 4) and corn.end % 12 in (8, 9, 10)  # planted Apr-May, off by Sep-Nov
    assert _phase(ia, "soybean").plant % 12 == 4 + 12 - 12  # May
    ks_corn = _phase(build_schedule([["corn"]], crops, kansas[1].climate), "corn")
    assert ks_corn.plant % 12 <= corn.plant % 12  # the warmer site plants no later


def test_winter_crops_are_sown_in_autumn_and_fallow_is_empty(kansas):
    crops = crops_by_id()
    s = build_schedule([["winter_wheat"], []], crops, kansas[1].climate)
    wheat = _phase(s, "winter_wheat")
    assert s.feasible and wheat.plant < 0 and wheat.plant % 12 in (8, 9, 10) and wheat.end % 12 in (5, 6)
    assert sum(1 for o in s.occupant if o is None) >= 12  # the fallow year really is empty


def test_infeasible_crops_are_rejected_with_a_reason(iowa):
    crops = crops_by_id()
    cotton = build_schedule([["cotton"]], crops, iowa[1].climate)
    assert not cotton.feasible and "cotton" in " ".join(cotton.issues).lower()
    canola = build_schedule([["canola"]], crops, iowa[1].climate)
    assert not canola.feasible and "winter" in " ".join(canola.issues).lower()


def test_cover_crop_fills_the_gap_without_overlapping_cash_crops(iowa):
    crops = crops_by_id()
    s = build_schedule([["corn", "cereal_rye"], ["soybean"]], crops, iowa[1].climate)
    rye, corn, soy = _phase(s, "cereal_rye"), _phase(s, "corn"), _phase(s, "soybean")
    assert s.feasible and rye.kind == "cover"
    assert corn.end < rye.plant <= rye.end < soy.plant
    assert 0.1 < rye.biomass_frac < 0.9  # a northern winter window gives partial growth, not a full stand
    assert all(0.0 <= c <= 1.0 for c in s.canopy)


def test_warming_scenario_moves_the_calendar(iowa):
    b, _ = iowa
    crops = crops_by_id()
    hot = analysis.context(b, {"temp_delta_c": 4.0})
    now = build_schedule([["winter_wheat"]], crops, iowa[1].climate)
    later = build_schedule([["winter_wheat"]], crops, hot.climate)
    assert _phase(later, "winter_wheat").end <= _phase(now, "winter_wheat").end
    assert sum(hot.climate.et0) > sum(iowa[1].climate.et0)


# ---------------------------------------------------------------------------- simulation


@pytest.mark.parametrize("years", [[["corn"], ["soybean"]], [["winter_wheat"], []], [["corn", "cereal_rye"], ["soybean", "cover_mix"]]])
def test_water_balance_closes(iowa, kansas, years):
    for _, ctx in (iowa, kansas):
        r = simulate(ctx, years, "conventional")
        inflow = sum(m["runoff_mm"] + m["drainage_mm"] + m["transpiration_mm"] + m["soil_evap_mm"] for m in r["months"])
        supplied = r["n_years"] * (sum(ctx.climate.precip)) + sum(m["irrigation_mm"] for m in r["months"]) * ctx.irrigation_efficiency
        storage = (r["months"][-1]["soil_water_frac"] - r["months"][0]["soil_water_frac"]) * ctx.taw_profile_mm
        # at steady state, water in = water out (within one month of storage change)
        assert inflow == pytest.approx(supplied, abs=0.06 * supplied + abs(storage) + 15)
        assert all(0 <= m["soil_water_frac"] <= 1 and m["transpiration_mm"] <= m["demand_mm"] + 0.1 for m in r["months"])


def test_cover_crops_and_no_till_protect_soil(iowa):
    _, ctx = iowa
    bare = simulate(ctx, [["corn"], ["soybean"]], "conventional")["metrics"]
    covered = simulate(ctx, [["corn", "cereal_rye"], ["soybean", "cereal_rye"]], "conventional")["metrics"]
    notill = simulate(ctx, [["corn"], ["soybean"]], "no_till")["metrics"]
    assert covered["soil_loss_t_ha_yr"] < bare["soil_loss_t_ha_yr"]
    assert covered["bare_months_per_year"] < bare["bare_months_per_year"]
    assert covered["n_leaching_kg_ha_yr"] < bare["n_leaching_kg_ha_yr"]
    assert covered["soc_change_t_ha_yr"] > bare["soc_change_t_ha_yr"]
    assert covered["runoff_mm_yr"] < bare["runoff_mm_yr"]
    assert notill["soil_loss_t_ha_yr"] < 0.5 * bare["soil_loss_t_ha_yr"]
    assert 0.5 < bare["soil_loss_tons_ac_yr"] < 12  # plausible for tilled corn-soybean on a 2% slope


def test_legumes_cut_purchased_nitrogen_and_diversity_breaks_pests(iowa):
    _, ctx = iowa
    corn = simulate(ctx, [["corn"]], "conventional")
    cs = simulate(ctx, [["corn"], ["soybean"]], "conventional")
    cso = simulate(ctx, [["corn"], ["soybean"], ["oats", "crimson_clover"]], "conventional")
    assert corn["metrics"]["n_fertilizer_kg_ha_yr"] > cs["metrics"]["n_fertilizer_kg_ha_yr"]
    assert corn["metrics"]["pest_break_score"] < cs["metrics"]["pest_break_score"] < cso["metrics"]["pest_break_score"]
    assert corn["pests"]["short_breaks"] and corn["economics"][0]["yield_factors"]["rotation"] < 1.0


def test_irrigation_respects_allocation_and_low_water_crops_use_less(kansas):
    b, ctx = kansas
    corn = simulate(ctx, [["corn"]], "conventional", with_history=True)
    assert 0 < corn["metrics"]["irrigation_mm_yr"] <= ctx.allocation_mm + 1
    assert max(corn["history"]["irrigation_mm"]) <= ctx.allocation_mm + 1
    assert len(corn["history"]["years"]) == len(ctx.climate.years) - 1
    assert corn["history"]["total_sd_per_acre"] >= corn["history"]["weather_sd_per_acre"] > 0
    # with water unlimited, each crop pumps what it needs: corn most, sorghum less, wheat-fallow least
    free = analysis.context(b, None, {"water_allocation_mm": 2000})
    need = {name: simulate(free, years, "conventional")["metrics"] for name, years in
            {"corn": [["corn"]], "sorghum": [["sorghum"]], "wheat_fallow": [["winter_wheat"], []]}.items()}
    assert need["corn"]["water_stress_pct"] < 3
    assert need["corn"]["irrigation_mm_yr"] > need["sorghum"]["irrigation_mm_yr"] > need["wheat_fallow"]["irrigation_mm_yr"]
    assert 350 < need["corn"]["irrigation_mm_yr"] < 750  # 14-30 in gross: the published range for southwest Kansas corn


def test_fallow_stores_water_for_the_next_crop(kansas):
    b, _ = kansas
    dry = analysis.context(b, None, {"irrigation_available": False})
    annual = simulate(dry, [["winter_wheat"]], "reduced")
    fallow = simulate(dry, [["winter_wheat"], []], "reduced")
    y_annual = annual["economics"][0]["yield_factors"]["water"]
    y_fallow = fallow["economics"][0]["yield_factors"]["water"]
    assert y_fallow >= y_annual  # the agronomic reason wheat-fallow exists


def test_every_metric_is_finite_for_every_farm(farm_ids):
    for fid in farm_ids:
        b = analysis.bundle(fid)
        base = b["farm"]["baseline_rotation"]
        r = simulate(analysis.context(b), base["years"], base["tillage"], with_history=True)
        assert r["feasible"], (fid, r["issues"])
        for key, value in r["metrics"].items():
            assert value is None or value == value, (fid, key)  # no NaN
        assert 0 <= r["metrics"]["mean_ground_cover_pct"] <= 100
        assert len(r["months"]) == 12 * r["n_years"]
