"""Rotation engine, scenario simulator and REST API: the challenge requirements as assertions."""
from __future__ import annotations

import datetime as dt
import math

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import analysis
from app.services.nasa_connectors import power
from app.services.rotation_engine import engine, scoring
from app.services.scenario_simulator import simulator

client = TestClient(app)
API = "/api/v1"
PILLARS = ("why", "evidence", "benefits", "gaps", "risks")


@pytest.fixture(scope="module")
def comparisons(farm_ids):
    return {fid: analysis.compare(fid) for fid in farm_ids}


# ----------------------------------------------------------------- challenge requirements


def test_at_least_three_strategies_always_including_the_baseline(comparisons):
    for fid, out in comparisons.items():
        roles = [s["role"] for s in out["strategies"]]
        assert len(roles) >= 3, fid
        assert roles[0] == "baseline" and roles.count("baseline") == 1, fid
        base = out["strategies"][0]
        assert base["years"] == analysis.bundle(fid)["farm"]["baseline_rotation"]["years"]
        signatures = {(str(s["years"]), s["tillage"]) for s in out["strategies"]}
        assert len(signatures) == len(roles), f"{fid}: strategies must differ from each other"


def test_every_strategy_explains_all_five_dimensions(comparisons):
    for fid, out in comparisons.items():
        for s in out["strategies"]:
            ex = s["explanation"]
            assert set(PILLARS) <= set(ex), (fid, s["role"])
            assert ex["why"] and all(r["text"] for r in ex["why"])
            assert ex["evidence"] and any(e["kind"] == "observed" for e in ex["evidence"])
            assert any(e["kind"] == "modelled" for e in ex["evidence"])
            assert ex["gaps"]["items"] and ex["gaps"]["statement"]
            assert ex["risks"] and all(r["who"] and r["title"] for r in ex["risks"])
            if s["role"] != "baseline":
                items = ex["benefits"]["items"]
                assert len(items) >= 8, (fid, s["role"])
                metrics = {b["metric"] for b in items}
                # the benefits the challenge names: water, organic matter, N, infiltration, erosion, bare soil, pests, income
                assert {"om_change_pct_points_10yr", "n_fertilizer_kg_ha_yr", "infiltration_pct", "soil_loss_tons_ac_yr",
                        "bare_months_per_year", "pest_break_score", "net_return_per_acre_yr"} <= metrics
                assert all(b["direction"] in {"better", "worse", "same"} for b in items)


def test_evidence_cites_nasa_and_usda_sources(comparisons):
    for fid, out in comparisons.items():
        sources = " ".join(str(e["source"]) for s in out["strategies"] for e in s["explanation"]["evidence"])
        assert "NASA" in sources and "USDA" in sources, fid


def test_gaps_disclose_what_satellites_cannot_see(comparisons):
    out = next(iter(comparisons.values()))
    gap_ids = {g["id"] for g in out["strategies"][1]["explanation"]["gaps"]["items"]}
    assert {"compaction", "biology", "drainage", "genetics", "contracts", "within_field"} <= gap_ids
    conf = out["strategies"][1]["explanation"]["gaps"]["confidence"]
    assert all(0 < conf[d]["combined"] <= 1 for d in scoring.DIMENSIONS)


def test_alternatives_address_each_farms_known_problem(comparisons):
    ks = comparisons["ogallala-ks"]["strategies"]
    assert min(s["metrics"]["irrigation_mm_yr"] for s in ks[1:]) < ks[0]["metrics"]["irrigation_mm_yr"]
    for fid in ("cornbelt-ia", "delta-ms", "palouse-wa"):
        s = comparisons[fid]["strategies"]
        assert min(x["metrics"]["soil_loss_t_ha_yr"] for x in s[1:]) < s[0]["metrics"]["soil_loss_t_ha_yr"], fid
        assert min(x["metrics"]["bare_months_per_year"] for x in s[1:]) < s[0]["metrics"]["bare_months_per_year"], fid


def test_scores_are_bounded_and_ranked(comparisons):
    for out in comparisons.values():
        fits = {s["id"]: s["fit"]["fit"] for s in out["strategies"]}
        assert all(0 <= f <= 100 for f in fits.values())
        assert [fits[i] for i in out["ranking"]] == sorted(fits.values(), reverse=True)
        for s in out["strategies"]:
            assert all(0 <= s["scores"][d] <= 100 for d in scoring.DIMENSIONS)
            assert sum(s["fit"]["weights"].values()) == pytest.approx(1.0, abs=0.01)


def test_vulnerability_calendar_covers_every_month(comparisons):
    for out in comparisons.values():
        for s in out["strategies"]:
            cells = s["vulnerability"]["cells"]
            assert len(cells) == 12 * s["n_years"]
            assert all(0 <= v <= 1 for c in cells for v in c["risks"].values())
            assert s["vulnerability"]["summary"]["headline"]


# ------------------------------------------------------------------ priorities & constraints


def test_priorities_change_the_recommendation():
    water = analysis.compare("ogallala-ks", priorities={"water": 10, "soil": 1, "erosion": 1, "pest": 1, "income": 1})
    money = analysis.compare("ogallala-ks", priorities={"water": 0, "soil": 0, "erosion": 0, "pest": 0, "income": 10})
    top_w = next(s for s in water["strategies"] if s["id"] == water["ranking"][0])
    top_m = next(s for s in money["strategies"] if s["id"] == money["ranking"][0])
    assert top_w["metrics"]["irrigation_mm_yr"] <= top_m["metrics"]["irrigation_mm_yr"]
    assert top_m["metrics"]["net_return_per_acre_yr"] >= top_w["metrics"]["net_return_per_acre_yr"]
    assert top_w["scores"]["water"] >= top_m["scores"]["water"]


def test_constraints_are_honoured():
    out = analysis.compare("cornbelt-ia", constraints={"exclude_crops": ["alfalfa", "sorghum"], "allow_cover_crops": False,
                                                         "allow_tillage_change": False})
    for s in out["strategies"][1:]:
        ids = {p["crop_id"] for p in s["phases"]}
        assert not ids & {"alfalfa", "sorghum"}
        assert all(p["kind"] != "cover" for p in s["phases"])
        assert s["tillage"] == out["strategies"][0]["tillage"]
    cautious = analysis.compare("cornbelt-ia", constraints={"risk_tolerance": "low"})
    bold = analysis.compare("cornbelt-ia", constraints={"risk_tolerance": "high"})
    assert sum(len(s["fit"]["penalties"]) for s in bold["strategies"]) <= sum(len(s["fit"]["penalties"]) for s in cautious["strategies"])


def test_rainfed_override_removes_irrigation():
    out = analysis.compare("ogallala-ks", constraints={"irrigation_available": False})
    assert all(s["metrics"]["irrigation_mm_yr"] == 0 for s in out["strategies"])


def test_user_baseline_and_custom_rotation_are_scored_alongside():
    out = analysis.compare("cornbelt-ia", baseline_override={"years": [["corn"]], "tillage": "conventional"},
                           custom_strategies=[{"name": "My idea", "years": [["corn"], ["soybean"], ["oats", "crimson_clover"]]}])
    assert out["strategies"][0]["years"] == [["corn"]]
    mine = out["strategies"][-1]
    assert mine["role"] == "custom" and mine["title"] == "My idea" and mine["explanation"]["benefits"]["items"]
    with pytest.raises(analysis.InvalidRotation):
        analysis.compare("cornbelt-ia", custom_strategies=[{"years": [["unobtainium"]]}])


def test_rotation_names_and_month_labels():
    assert engine.rotation_name([["corn"]]) == "Continuous corn"
    assert engine.rotation_name([["winter_wheat"], []]) == "Winter wheat → Fallow"
    assert engine.month_range([10, 11, 0, 1]) == "Nov-Feb"
    assert engine.month_range([3, 4, 5, 9]) == "Apr-Jun, Oct"


# ------------------------------------------------------------------------------ scenarios


def _specs(out):
    return [{"id": s["id"], "role": s["role"], "name": s["name"], "years": s["years"], "tillage": s["tillage"]} for s in out["strategies"]]


def test_hot_dry_scenario_hurts_a_rainfed_baseline(comparisons):
    specs = _specs(comparisons["cornbelt-ia"])
    res = simulator.stress_test("cornbelt-ia", specs, {"temp_delta_c": 3.0, "rain_pct": -30.0})
    base = res["strategies"][0]
    assert base["metrics"]["net_return_per_acre_yr"]["scenario"] < base["metrics"]["net_return_per_acre_yr"]["today"]
    assert base["metrics"]["water_stress_pct"]["scenario"] >= base["metrics"]["water_stress_pct"]["today"]
    shift = res["climate_shift"]
    assert shift["heat_days_35"]["delta"] > 0 and shift["frost_days"]["delta"] < 0 and shift["reference_et_mm"]["delta"] > 0
    assert res["verdict"] and len(res["ranking_scenario"]) == len(specs)


def test_water_cap_cuts_pumping_and_heavier_storms_raise_runoff(comparisons):
    specs = _specs(comparisons["ogallala-ks"])[:2]
    cap = simulator.stress_test("ogallala-ks", specs, {"water_cap_pct": 50.0})
    base = cap["strategies"][0]
    assert base["metrics"]["irrigation_mm_yr"]["scenario"] < base["metrics"]["irrigation_mm_yr"]["today"]
    assert cap["climate_shift"]["irrigation_allocation_mm"]["delta"] < 0
    storm = simulator.stress_test("delta-ms", _specs(comparisons["delta-ms"])[:2], {"storm_intensity_pct": 50.0})
    b = storm["strategies"][0]["metrics"]
    assert b["runoff_mm_yr"]["scenario"] > b["runoff_mm_yr"]["today"]
    assert b["soil_loss_tons_ac_yr"]["scenario"] > b["soil_loss_tons_ac_yr"]["today"]


def test_neutral_scenario_changes_nothing(comparisons):
    specs = _specs(comparisons["palouse-wa"])[:2]
    res = simulator.stress_test("palouse-wa", specs, {})
    assert all(abs(s["fit"]["delta"]) < 0.01 for s in res["strategies"]) and not res["ranking_changed"]


def test_sweep_returns_one_value_per_step(comparisons):
    specs = _specs(comparisons["ogallala-ks"])[:3]
    out = simulator.sweep("ogallala-ks", specs, "water_cap_pct", steps=5)
    assert out["values"] == [0.0, 25.0, 50.0, 75.0, 100.0]
    assert all(len(s["fit"]) == 5 and len(s["net"]) == 5 for s in out["series"])
    base_net = out["series"][0]["net"]
    assert base_net[-1] >= base_net[0]  # more water never hurts irrigated corn


def test_scenario_values_are_clamped():
    sc = simulator.clean_scenario({"temp_delta_c": 99, "rain_pct": -999, "water_cap_pct": None})
    assert sc == {"temp_delta_c": 5.0, "rain_pct": -50.0, "storm_intensity_pct": 0.0, "water_cap_pct": 100.0}


# ------------------------------------------------------------------------------------ API


def test_health_and_meta():
    assert client.get("/health").json()["status"] == "ok"
    meta = client.get(f"{API}/meta").json()
    assert "never replaces" in meta["disclaimer"]
    assert len(meta["sources"]) >= 26


def test_farm_endpoints(farm_ids):
    farms = client.get(f"{API}/farms").json()
    assert {f["id"] for f in farms} == set(farm_ids)
    ov = client.get(f"{API}/farms/{farm_ids[0]}")
    assert ov.status_code == 200
    body = ov.json()
    assert len(body["climate"]["monthly"]["precip"]) == 12
    assert len(body["fusion"]["layers"]) >= 10 and body["insights"]["facts"]
    assert len(body["hazards"]["months"]) == 12
    vul = client.get(f"{API}/farms/{farm_ids[0]}/vulnerability").json()
    assert vul["baseline"]["calendar"]["cells"] and set(vul["hazard_labels"]) == {"storm", "heat", "frost", "drought", "leaching"}


def test_reference_endpoints():
    assert len(client.get(f"{API}/nasa/gibs/layers").json()["layers"]) >= 10
    assert client.get(f"{API}/nasa/missions").json()["missions"]
    assert client.get(f"{API}/nasa/sources").json()["status_counts"]["live"] >= 5
    cat = client.get(f"{API}/soil-crops/catalog").json()
    assert len(cat["crops"]) >= 20 and len(cat["tillage_systems"]) == 3
    opts = client.get(f"{API}/rotations/options").json()
    assert [d["id"] for d in opts["dimensions"]] == scoring.DIMENSIONS and opts["priority_presets"]
    presets = client.get(f"{API}/scenarios/presets").json()
    assert set(presets["limits"]) == {"temp_delta_c", "rain_pct", "storm_intensity_pct", "water_cap_pct"}
    suit = client.get(f"{API}/soil-crops/suitability/cornbelt-ia").json()
    by_id = {r["crop_id"]: r for r in suit["rows"]}
    assert by_id["corn"]["feasible"] and not by_id["cotton"]["feasible"]
    assert client.get(f"{API}/soil-crops/market/cornbelt-ia").json()["rows"]


def test_compare_and_stress_test_over_http():
    r = client.post(f"{API}/rotations/compare", json={"field_id": "palouse-wa", "priorities": {"erosion": 10}})
    assert r.status_code == 200 and "server-timing" in r.headers
    body = r.json()
    assert len(body["strategies"]) >= 3 and body["disclaimer"]
    specs = [{"id": s["id"], "role": s["role"], "years": s["years"], "tillage": s["tillage"]} for s in body["strategies"][:2]]
    st = client.post(f"{API}/scenarios/stress-test", json={"field_id": "palouse-wa", "strategies": specs,
                                                            "scenario": {"temp_delta_c": 2, "rain_pct": -15}})
    assert st.status_code == 200 and len(st.json()["strategies"]) == 2
    sw = client.post(f"{API}/scenarios/sweep", json={"field_id": "palouse-wa", "strategies": specs, "parameter": "rain_pct", "steps": 3})
    assert sw.status_code == 200 and sw.json()["values"] == [-50.0, -10.0, 30.0]


def test_errors_are_uniform_json():
    missing = client.get(f"{API}/farms/atlantis")
    assert missing.status_code == 404 and missing.json()["error"] == "field_not_found" and missing.json()["hint"]
    bad_crop = client.post(f"{API}/rotations/compare", json={"field_id": "cornbelt-ia", "custom_strategies": [{"years": [["kelp"]]}]})
    assert bad_crop.status_code == 422 and bad_crop.json()["error"] == "invalid_rotation"
    bad_body = client.post(f"{API}/rotations/compare", json={"field_id": "cornbelt-ia", "priorities": {"water": 11}})
    assert bad_body.status_code == 422 and bad_body.json()["error"] == "invalid_request"
    offline = client.get(f"{API}/nasa/power", params={"lat": 10.0, "lon": 10.0})
    assert offline.status_code == 503 and offline.json()["error"] == "data_source_unavailable"


def test_openapi_contract_lists_every_route_group():
    spec = client.get("/openapi.json").json()
    paths = set(spec["paths"])
    for needed in ("/api/v1/farms", "/api/v1/farms/custom", "/api/v1/nasa/power", "/api/v1/nasa/gibs/layers",
                   "/api/v1/soil-crops/catalog", "/api/v1/rotations/compare", "/api/v1/scenarios/stress-test"):
        assert needed in paths
    assert "CompareResponse" in spec["components"]["schemas"] and "Strategy" in spec["components"]["schemas"]


# ------------------------------------------------------------ custom field (mocked services)


def _fake_services(request: httpx.Request) -> httpx.Response:
    """Stand-ins for every live service a custom field touches. Daymet and MODIS are 'down'."""
    host = request.url.host
    if host == "power.larc.nasa.gov":
        days, cols = [], {name: {} for name in power.PARAMETERS}
        for year in range(2019, 2024):
            for doy in range(365):
                date = (dt.date(year, 1, 1) + dt.timedelta(days=doy)).strftime("%Y%m%d")
                season = math.sin(2 * math.pi * (doy - 105) / 365)
                days.append(date)
                cols["T2M_MAX"][date] = 16 + 15 * season
                cols["T2M_MIN"][date] = 4 + 14 * season
                rain = 14.0 if doy % 5 == 0 and 90 < doy < 290 else (3.0 if doy % 9 == 0 else 0.0)
                cols["PRECTOTCORR"][date] = rain
                cols["IMERG_PRECTOT"][date] = rain * 1.1
                for name, value in (("GWETROOT", 0.5 + 0.1 * season), ("GWETTOP", 0.5), ("ALLSKY_SFC_SW_DWN", 15), ("RH2M", 60), ("WS2M", 3), ("TS", 12)):
                    cols[name][date] = value
        return httpx.Response(200, json={"geometry": {"coordinates": [-97.4, 41.2, 500]}, "properties": {"parameter": cols}})
    if host == "sdmdataaccess.sc.egov.usda.gov":
        if b"corestrictions" in request.content:
            return httpx.Response(200, json={})
        header = ["mukey", "muname", "cokey", "compname", "comppct_r", "hydgrp", "drainagecl", "slope_r", "tfact", "taxorder", "nirrcapcl",
                  "hzdept_r", "hzdepb_r", "sandtotal_r", "silttotal_r", "claytotal_r", "om_r", "dbthirdbar_r", "awc_r", "ksat_r",
                  "ph1to1h2o_r", "kwfact", "ec_r", "cec7_r"]
        row = ["7", "Mock silt loam, 0 to 2 percent slopes", "70", "Mockton", "90", "B", "Well drained", "1", "5", "Mollisols", "2",
               "0", "150", "15", "62", "23", "3.0", "1.32", "0.20", "9", "6.6", ".32", "0", "20"]
        return httpx.Response(200, json={"Table": [header, row]})
    if host == "api.opentopodata.org":
        return httpx.Response(200, json={"results": [{"elevation": 500.0}] * 9})
    if host == "nassgeodata.gmu.edu":
        year = int(request.url.params["year"])
        code, name = (1, "Corn") if year % 2 == 0 else (5, "Soybeans")
        return httpx.Response(200, text=f'<r>{{x: 1, y: 2, value: {code}, category: "{name}"}}</r>')
    if host == "modis.ornl.gov":
        return httpx.Response(400, json="No data available")
    return httpx.Response(503)  # Daymet


def test_custom_field_is_built_from_live_layers_and_degrades_gracefully(mock_http):
    mock_http(_fake_services)
    r = client.post(f"{API}/farms/custom", json={"lat": 41.2, "lon": -97.4, "name": "Test quarter"})
    assert r.status_code == 200, r.text
    field = r.json()
    assert field["kind"] == "custom" and field["farm"]["name"] == "Test quarter"
    assert field["soil"]["series"] == "Mockton" and field["soil"]["texture_class"] == "silt loam"
    assert field["farm"]["baseline_rotation"]["years"] == [["corn"], ["soybean"]]  # read off the crop history
    assert not field["farm"].get("baseline_assumed")
    # the two services that were down are reported, not fatal
    assert {"daymet", "modis_ndvi"} <= {i["layer"] for i in field["issues"]}
    assert field["fusion"]["precip"]["has_ground"] is False and field["vegetation"] is None
    by_id = {row["id"]: row for row in field["fusion"]["layers"]}
    assert by_id["ground_precip"]["access"] == "unavailable" and by_id["ssurgo"]["access"] == "live"
    assert by_id["soil_moisture"]["access"] == "proxy"

    compared = client.post(f"{API}/rotations/compare", json={"field_id": field["id"]}).json()
    assert len(compared["strategies"]) >= 3 and compared["strategies"][0]["role"] == "baseline"
    gap_ids = {g["id"] for g in compared["strategies"][1]["explanation"]["gaps"]["items"]}
    assert {"layer_ground_precip", "layer_ndvi", "yield_reference", "market_unverified"} <= gap_ids  # missing data is disclosed
    assert client.get(f"{API}/farms/{field['id']}").status_code == 200  # the id keeps working


def test_custom_field_fails_cleanly_without_nasa_power(mock_http):
    mock_http(lambda request: httpx.Response(503))
    r = client.post(f"{API}/farms/custom", json={"lat": 12.3, "lon": 45.6})
    assert r.status_code == 503 and r.json()["error"] == "data_source_unavailable"


def test_explanation_items_have_unique_ids(comparisons):
    for fid, out in comparisons.items():
        for s in out["strategies"]:
            ex = s["explanation"]
            for name in ("risks", "evidence"):
                ids = [item["id"] for item in ex[name]]
                assert len(ids) == len(set(ids)), (fid, s["role"], name)
            gap_ids = [g["id"] for g in ex["gaps"]["items"]]
            assert len(gap_ids) == len(set(gap_ids)), (fid, s["role"])
