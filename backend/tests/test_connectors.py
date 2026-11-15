"""NASA and global connectors against mocked HTTP: parsing, chunking, fallbacks, provenance."""
from __future__ import annotations

import datetime as dt
import json
import math

import httpx
import pytest

from app.services.nasa_connectors import base, gibs, land_products, missions, power, terrain
from app.services.global_connectors import gaez, ghcn, sentinel2, soilgrids
from app.utils import geo


def _power_payload() -> dict:
    days = ["20230101", "20230102", "20230103"]
    cols = {name: {d: 1.0 + i for i, d in enumerate(days)} for name in power.PARAMETERS}
    cols["IMERG_PRECTOT"]["20230102"] = -999.0
    return {"geometry": {"coordinates": [100.32, 6.08, 4.0]}, "properties": {"parameter": cols}}


def test_power_parses_series_and_masks_fill_values(mock_http):
    calls = mock_http(lambda req: httpx.Response(200, json=_power_payload()))
    out = power.fetch_daily(6.08, 100.32, 2023, 2023)
    assert out["dates"] == ["20230101", "20230102", "20230103"]
    assert out["series"]["tmax"] == [1.0, 2.0, 3.0]
    assert out["series"]["precip_imerg"][1] is None  # -999 fill becomes missing, never a number
    assert out["grid_elevation_m"] == 4.0
    assert out["provenance"]["access"] == "live"
    assert "time-standard=UTC" in str(calls[0].url)  # IMERG is only served on UTC


def test_second_call_is_served_from_cache(mock_http):
    calls = mock_http(lambda req: httpx.Response(200, json=_power_payload()))
    power.fetch_daily(6.08, 100.32, 2023, 2023)
    again = power.fetch_daily(6.08, 100.32, 2023, 2023)
    assert len(calls) == 1
    assert again["provenance"]["access"] == "cache"


def test_unreachable_source_raises_connector_error(mock_http):
    mock_http(lambda req: httpx.Response(503))
    with pytest.raises(base.ConnectorError):
        base.fetch("unit", "https://example.invalid/x", retries=0)


def test_client_errors_are_not_retried(mock_http):
    calls = mock_http(lambda req: httpx.Response(400, json="No data"))
    with pytest.raises(base.ConnectorError):
        base.fetch("unit", "https://example.invalid/x", retries=3)
    assert len(calls) == 1


def test_land_product_series_is_chunked_scaled_and_masked(mock_http):
    dates = [{"modis_date": f"A2023{d:03d}", "calendar_date": f"2023-{1 + d // 32:02d}-{1 + d % 28:02d}"} for d in range(1, 370, 16)]

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/dates"):
            return httpx.Response(200, json={"dates": dates})
        start, end = req.url.params["startDate"], req.url.params["endDate"]
        rows = [d for d in dates if start <= d["modis_date"] <= end]
        return httpx.Response(200, json={"subset": [{"calendar_date": d["calendar_date"], "data": [5000 if i else -3000]}
                                                    for i, d in enumerate(rows)]})

    calls = mock_http(handler)
    out = land_products.fetch_series("ndvi", 4.52, 101.42, "2023-01-01", "2023-12-31")
    subset_calls = [c for c in calls if c.url.path.endswith("/subset")]
    assert len(subset_calls) == 3  # 24 composites, 10 per request
    assert len(out["values"]) == len(dates)
    assert 0.5 in out["values"] and None in out["values"]  # scaled by 0.0001; fill value masked
    assert out["provenance"]["resolution_m"] == 250


def test_land_product_without_coverage_is_remembered(mock_http):
    calls = mock_http(lambda req: httpx.Response(400, json="No SPL3SMP_E data available"))
    assert land_products.available_dates("SPL3SMP_E", 38.0, -100.0) == []
    assert land_products.available_dates("SPL3SMP_E", 38.0, -100.0) == []
    assert len(calls) == 1


def test_smap_adapter_falls_back_to_labelled_proxy(mock_http):
    mock_http(lambda req: httpx.Response(400, json="No data"))
    daily = {"dates": ["20230101"], "series": {"wet_root": [0.4], "wet_top": [0.5]}}
    out = missions.smap_soil_moisture(38.0, -100.0, daily, "2023-01-01", "2023-12-31")
    assert out["kind"] == "merra2_proxy"
    assert out["provenance"]["access"] == "proxy"
    assert "SMAP" in out["provenance"]["note"]


def test_grace_without_a_curated_region_is_labelled_unavailable():
    out = missions.grace_water_storage(6.08, 100.32)
    assert out["tws_trend_cm_yr"] is None and out["provenance"]["access"] == "unavailable"
    assert "Malaysia" in out["provenance"]["note"]


def test_terrain_slope_from_srtm_window(mock_http):
    # a plane rising 1 m per 90 m to the east: slope must be 1/90 = 1.11 %
    def handler(req: httpx.Request) -> httpx.Response:
        pts = req.url.params["locations"].split("|")
        lons = [float(p.split(",")[1]) for p in pts]
        west = min(lons)
        step = (max(lons) - west) / 2
        return httpx.Response(200, json={"results": [{"elevation": 100 + round((lo - west) / step)} for lo in lons]})

    mock_http(handler)
    t = terrain.fetch_terrain(40.0, -95.0)
    assert t["slope_pct"] == pytest.approx(1.11, abs=0.02)
    assert t["elevation_m"] == 101.0


def _soilgrids_payload(clay):
    """SoilGrids v2 JSON: integer values with a d_factor per property."""
    top = {"sand": 300, "silt": 250, "clay": None if clay is None else clay * 10, "soc": 200, "bdod": 130, "phh2o": 48,
           "cec": 150, "wv0033": 400, "wv1500": 250, "cfvo": 0}
    factors = {"sand": 10, "silt": 10, "clay": 10, "soc": 10, "bdod": 100, "phh2o": 10, "cec": 10, "wv0033": 10, "wv1500": 10, "cfvo": 10}
    layers = [{"name": name, "unit_measure": {"d_factor": factors[name]},
               "depths": [{"label": label, "values": {"mean": value}} for label, _a, _b in soilgrids.DEPTHS]}
              for name, value in top.items()]
    return {"properties": {"layers": layers}}


def test_soilgrids_harmonises_and_derives_hydrology(mock_http):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/classification/query"):
            return httpx.Response(200, json={"wrb_class_name": "Gleysols", "wrb_class_probability": [["Gleysols", 40]]})
        return httpx.Response(200, json=_soilgrids_payload(45.0))

    mock_http(handler)
    s = soilgrids.fetch_soil_profile(6.08, 100.32)
    assert s["clay_pct"] == pytest.approx(45.0, abs=0.2)
    assert s["organic_matter_pct"] == pytest.approx(20 / 10 * 1.724, abs=0.01)  # SOC g/kg -> OM %
    assert s["ph"] == 4.8 and s["texture_class"] == "clay"
    assert s["hydrologic_group"] in {"C", "D"}  # heavy marine clay drains slowly
    assert s["series"].startswith("Gleysols") and s["sample_offset_m"] == 0
    assert s["provenance"]["resolution_m"] == 250 and "ksat_um_s" in s["derived"]


def test_soilgrids_masked_pixel_moves_to_the_nearest_valid_one(mock_http):
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/classification/query"):
            return httpx.Response(200, json={})
        seen.append(req.url.params["lat"])
        return httpx.Response(200, json=_soilgrids_payload(None if len(seen) == 1 else 20.0))

    mock_http(handler)
    s = soilgrids.fetch_soil_profile(4.47, 101.38)
    assert len(seen) == 2 and 250 < s["sample_offset_m"] < 350
    assert "masked" in s["provenance"]["note"] and s["series"].startswith("Unclassified")


def test_soilgrids_with_no_valid_pixel_raises(mock_http):
    mock_http(lambda req: httpx.Response(200, json=_soilgrids_payload(None)))
    with pytest.raises(base.ConnectorError):
        soilgrids.fetch_soil_profile(1.0, 104.0)


def test_gaez_reads_baseline_and_future_suitability(mock_http):
    catalogue = [{"objectid": 1, "year": "1981-2010", "model": "CRUTS32", "rcp": "Historical", "water_supply": "Rainfed"}]
    catalogue += [{"objectid": 10 + i, "year": "2041-2070", "model": m, "rcp": "RCP8.5", "water_supply": "Rainfed"}
                  for i, m in enumerate(["GFDL-ESM2M", "HadGEM2-ES", "IPSL-CM5A-LR"])]
    values = {1: 6363, 10: 5000, 11: 5400, 12: 7000}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/query"):
            return httpx.Response(200, json={"features": [{"attributes": a} for a in catalogue]})
        oid = json.loads(req.url.params["mosaicRule"])["lockRasterIds"][0]
        return httpx.Response(200, json={"value": str(values[oid])})

    mock_http(handler)
    crops = {"rice": {"gaez": {"crop": "Wetland rice", "irrigated": True}}, "chili": {"gaez": None}}
    out = gaez.crop_suitability(6.10, 100.40, crops)
    row = out["crops"]["rice"]
    assert set(out["crops"]) == {"rice"}  # crops GAEZ does not model are skipped
    assert row["si"] == 6363 and row["class"] == "Good"
    assert row["si_2050s"] == 5400 and row["change_2050s"] == -963  # median of the climate models
    assert out["provenance"]["access"] == "live"


def test_gaez_outage_is_reported_not_fatal(mock_http):
    mock_http(lambda req: httpx.Response(503))
    out = gaez.crop_suitability(6.1, 100.4, {"rice": {"gaez": {"crop": "Wetland rice"}}}, with_future=False)
    assert out["crops"] == {} and out["provenance"]["access"] == "unavailable"


def test_ghcn_picks_the_nearest_gauge_and_keeps_missing_days_missing(mock_http):
    station, dist = ghcn.nearest_station(6.08, 100.32)
    assert dist <= ghcn.MAX_DISTANCE_KM
    assert ghcn.nearest_station(40.0, -100.0) is None
    rows = [{"DATE": "2023-01-02", "PRCP": "12.5", "TMAX": "33.1", "TMIN": "23.0"},
            {"DATE": "2023-01-01", "TMAX": "32.0", "TMIN": "22.5"}]
    mock_http(lambda req: httpx.Response(200, json=rows))
    out = ghcn.fetch_gauge(6.08, 100.32, 2023, 2023)
    assert out["dates"] == ["20230101", "20230102"]
    assert out["series"]["precip"] == [None, 12.5]  # an unreported day is not a dry day
    assert out["station"]["id"] == station["id"] and out["station"]["rain_days_reported"] == 1


def test_sentinel2_ndvi_masks_clouds_and_applies_the_boa_offset(mock_http):
    days = [dt.date(2023, 1, 1) + dt.timedelta(days=5 * i) for i in range(10)]
    features = [{"id": f"S2_{i}", "properties": {"datetime": d.isoformat() + "T03:00:00Z", "eo:cloud_cover": 20,
                                                 "s2:processing_baseline": "05.09", "s2:mgrs_tile": "47NPG"}}
                for i, d in enumerate(days)]

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return httpx.Response(200, json={"features": features, "links": []})
        i = int(req.url.params["item"].split("_")[1])
        scl = 9 if i == 3 else 4  # scene 3 is cloud over the pixel
        return httpx.Response(200, json={"values": [1500, 4000, scl]})

    mock_http(handler)
    out = sentinel2.fetch_ndvi(6.08, 100.32, "2023-01-01", "2023-03-01")
    assert len(out["values"]) == 9 and out["scenes_searched"] == 10
    assert out["values"][0] == pytest.approx((3000 - 500) / (3000 + 500), abs=1e-4)  # offset removed from both bands
    assert out["provenance"]["resolution_m"] == 10


def test_crop_cycles_counts_two_paddy_seasons_a_year():
    start = dt.date(2021, 1, 1)
    dates, values = [], []
    for k in range(0, 3 * 365, 6):
        dates.append((start + dt.timedelta(days=k)).isoformat())
        values.append(round(0.45 + 0.35 * math.sin(2 * math.pi * k / 182.5), 3))  # green-up and harvest twice a year
    cyc = sentinel2.crop_cycles({"dates": dates, "values": values, "provenance": {"dataset": "x"}})
    assert 1.7 <= cyc["cycles_per_year"] <= 2.3 and not cyc["evergreen"]
    flat = sentinel2.crop_cycles({"dates": dates, "values": [0.8] * len(dates), "provenance": {}})
    assert flat["cycles_per_year"] == 0 and flat["evergreen"]  # oil palm or forest


def test_gibs_catalogue_templates_are_complete():
    layers = gibs.catalogue()
    assert len(layers) >= 10
    for layer in layers:
        url = layer["tile_url"]
        assert layer["id"] in url and "{z}/{y}/{x}" in url and "{layer}" not in url and "{tms}" not in url
        assert ("{time}" in url) == (not (layer["temporal"] == "static" and not layer["start"]))


def test_texture_triangle():
    assert geo.usda_texture_class(20, 60, 20) == "silt loam"
    assert geo.usda_texture_class(90, 5, 5) == "sand"
    assert geo.usda_texture_class(20, 20, 60) == "clay"
    assert geo.usda_texture_class(40, 40, 20) == "loam"
