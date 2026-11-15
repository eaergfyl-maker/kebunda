"""Fusion, crop calendar and field simulation: physical sanity and agronomic direction."""
from __future__ import annotations

import pytest

from app.services import analysis
from app.services.fusion_engine import climate, harmonize
from app.services.rotation_engine.context import crops_by_id, rainfall_erosivity
from app.services.rotation_engine.schedule import build_schedule, is_tropical
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


def test_layer_inventory_scores_resolution_gap(kedah):
    b, _ = kedah
    rows = {r["id"]: r for r in b["layers"]}
    assert all(0.0 <= r["confidence"] <= 1.0 for r in rows.values())
    # a 9-36 km soil-moisture cell says less about one field than a 250 m soil grid or a 10 m Sentinel-2 pixel
    assert rows["soil_moisture"]["representativeness"] < rows["soil"]["representativeness"]
    assert {"gaez", "crop_cycles"} <= set(rows)
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


def test_malaysian_farms_run_in_tropical_mode(farm_ids):
    for fid in farm_ids:
        assert is_tropical(analysis.context(analysis.bundle(fid)).climate), fid


def test_two_paddy_seasons_chain_through_the_year(kedah):
    s = build_schedule([["rice", "rice"]], crops_by_id(), kedah[1].climate)
    first, second = [p for p in s.phases if p.id == "rice"]
    assert s.feasible and s.tropical
    assert second.plant == first.end + 1  # the second season follows straight on from the harvest
    assert all(3 <= p.end - p.plant + 1 <= 5 for p in (first, second))


def test_infeasible_rotations_are_rejected_with_a_reason(kelantan):
    crops = crops_by_id()
    rainfed_paddy = simulate(kelantan[1], [["rice"]])
    assert not rainfed_paddy["feasible"] and "irrigation" in " ".join(rainfed_paddy["issues"]).lower()
    crowded = build_schedule([["cassava", "kenaf", "chili"]], crops, kelantan[1].climate)
    assert not crowded.feasible and "months back to back" in " ".join(crowded.issues)


def test_cover_crop_fills_the_gap_without_overlapping_cash_crops(kelantan):
    s = build_schedule([["kenaf", "sunn_hemp"]], crops_by_id(), kelantan[1].climate)
    kenaf, hemp = _phase(s, "kenaf"), _phase(s, "sunn_hemp")
    assert s.feasible and hemp.kind == "cover"
    assert kenaf.end < hemp.plant <= hemp.end
    assert all(0.0 <= c <= 1.0 for c in s.canopy)


def test_highland_crops_suffer_in_lowland_heat(kedah, cameron):
    lowland = simulate(kedah[1], [["cabbage"]])["economics"][0]["yield_factors"]["heat"]
    highland = simulate(cameron[1], [["cabbage"]])["economics"][0]["yield_factors"]["heat"]
    assert highland > 0.9 > 0.6 > lowland  # why Malaysian cabbage comes from Cameron Highlands


def test_warming_scenario_adds_heat_stress_and_water_demand(kedah):
    b, ctx = kedah
    hot = analysis.context(b, {"temp_delta_c": 3.0})
    now = simulate(ctx, [["chili"]])["economics"][0]["yield_factors"]["heat"]
    later = simulate(hot, [["chili"]])["economics"][0]["yield_factors"]["heat"]
    assert later < now
    assert sum(hot.climate.et0) > sum(ctx.climate.et0)


# ---------------------------------------------------------------------------- simulation


@pytest.mark.parametrize("years", [[["sweet_corn", "long_bean"]], [["kenaf"], []], [["kenaf", "sunn_hemp"]], [["rice", "rice"]]])
def test_water_balance_closes(kedah, kelantan, years):
    for _, ctx in (kedah, kelantan):
        r = simulate(ctx, years, "conventional")
        if not r["feasible"]:
            continue  # paddy on the rainfed farm
        inflow = sum(m["runoff_mm"] + m["drainage_mm"] + m["transpiration_mm"] + m["soil_evap_mm"] for m in r["months"])
        supplied = r["n_years"] * (sum(ctx.climate.precip)) + sum(m["irrigation_mm"] for m in r["months"]) * ctx.irrigation_efficiency
        storage = (r["months"][-1]["soil_water_frac"] - r["months"][0]["soil_water_frac"]) * ctx.taw_profile_mm
        # at steady state, water in = water out (within one month of storage change)
        assert inflow == pytest.approx(supplied, abs=0.06 * supplied + abs(storage) + 15)
        assert all(0 <= m["soil_water_frac"] <= 1 and m["transpiration_mm"] <= m["demand_mm"] + 0.1 for m in r["months"])


def test_cover_crops_and_no_till_protect_soil(kelantan):
    _, ctx = kelantan
    bare = simulate(ctx, [["kenaf"]], "conventional")["metrics"]
    covered = simulate(ctx, [["kenaf", "mucuna"]], "conventional")["metrics"]
    notill = simulate(ctx, [["kenaf"]], "no_till")["metrics"]
    assert covered["soil_loss_t_ha_yr"] < bare["soil_loss_t_ha_yr"]
    assert covered["bare_months_per_year"] < bare["bare_months_per_year"]
    assert covered["n_leaching_kg_ha_yr"] < bare["n_leaching_kg_ha_yr"]
    assert covered["soc_change_t_ha_yr"] > bare["soc_change_t_ha_yr"]
    assert covered["runoff_mm_yr"] < bare["runoff_mm_yr"]
    assert notill["soil_loss_t_ha_yr"] < 0.5 * bare["soil_loss_t_ha_yr"]


def test_legumes_cut_purchased_nitrogen_and_diversity_breaks_pests(kelantan):
    _, ctx = kelantan
    corn = simulate(ctx, [["sweet_corn", "sweet_corn"]], "conventional")
    cg = simulate(ctx, [["sweet_corn", "groundnut"]], "conventional")
    mixed = simulate(ctx, [["sweet_corn", "groundnut"], ["sweet_potato", "long_bean"]], "conventional")
    assert corn["metrics"]["n_fertilizer_kg_ha_yr"] > cg["metrics"]["n_fertilizer_kg_ha_yr"]
    assert corn["metrics"]["pest_break_score"] < cg["metrics"]["pest_break_score"] < mixed["metrics"]["pest_break_score"]
    assert corn["pests"]["short_breaks"] and corn["economics"][0]["yield_factors"]["rotation"] < 1.0
    assert corn["pests"]["short_breaks"][0]["unit"] == "season"  # tropical breaks are counted in crop seasons


def test_paddy_needs_far_more_water_than_dryland_crops(kedah):
    b, ctx = kedah
    paddy = simulate(ctx, [["rice", "rice"]], "conventional", with_history=True)
    assert 0 < paddy["metrics"]["irrigation_mm_yr"] <= ctx.allocation_mm + 1
    assert max(paddy["history"]["irrigation_mm"]) <= ctx.allocation_mm + 1
    assert paddy["history"]["total_sd_per_ha"] >= paddy["history"]["weather_sd_per_ha"] >= 0
    dry = simulate(ctx, [["sweet_corn", "long_bean"]], "conventional")
    assert paddy["metrics"]["irrigation_mm_yr"] > dry["metrics"]["irrigation_mm_yr"] + 200
    assert paddy["metrics"]["deep_drainage_mm_yr"] > dry["metrics"]["deep_drainage_mm_yr"]  # percolation through the puddled layer
    capped = analysis.context(b, None, {"water_allocation_mm": 100})
    assert simulate(capped, [["rice", "rice"]])["metrics"]["irrigation_mm_yr"] <= 101


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
