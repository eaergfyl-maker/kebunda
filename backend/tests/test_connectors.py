"""NASA and USDA connectors against mocked HTTP: parsing, chunking, fallbacks, provenance."""
from __future__ import annotations

import httpx
import pytest

from app.services.nasa_connectors import base, gibs, land_products, missions, power, terrain
from app.services.usda_connectors import cropland, ground_truth, ssurgo
from app.utils import geo


def _power_payload() -> dict:
    days = ["20230101", "20230102", "20230103"]
    cols = {name: {d: 1.0 + i for i, d in enumerate(days)} for name in power.PARAMETERS}
    cols["IMERG_PRECTOT"]["20230102"] = -999.0
    return {"geometry": {"coordinates": [-100.9, 38.06, 870.0]}, "properties": {"parameter": cols}}


def test_power_parses_series_and_masks_fill_values(mock_http):
    calls = mock_http(lambda req: httpx.Response(200, json=_power_payload()))
    out = power.fetch_daily(38.06, -100.9, 2023, 2023)
    assert out["dates"] == ["20230101", "20230102", "20230103"]
    assert out["series"]["tmax"] == [1.0, 2.0, 3.0]
    assert out["series"]["precip_imerg"][1] is None  # -999 fill becomes missing, never a number
    assert out["grid_elevation_m"] == 870.0
    assert out["provenance"]["access"] == "live"
    assert "time-standard=UTC" in str(calls[0].url)  # IMERG is only served on UTC


def test_second_call_is_served_from_cache(mock_http):
    calls = mock_http(lambda req: httpx.Response(200, json=_power_payload()))
    power.fetch_daily(38.06, -100.9, 2023, 2023)
    again = power.fetch_daily(38.06, -100.9, 2023, 2023)
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
    out = land_products.fetch_series("ndvi", 42.0, -93.78, "2023-01-01", "2023-12-31")
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


def test_grace_regions_and_gaps():
    ks = missions.grace_water_storage(38.06, -100.9)
    assert ks["tws_trend_cm_yr"] < 0 and ks["provenance"]["access"] == "curated"
    nowhere = missions.grace_water_storage(-30.0, 25.0)
    assert nowhere["tws_trend_cm_yr"] is None and nowhere["provenance"]["access"] == "unavailable"


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


def test_ssurgo_harmonises_top_30_cm(mock_http):
    header = ["mukey", "muname", "cokey", "compname", "comppct_r", "hydgrp", "drainagecl", "slope_r", "tfact", "taxorder",
              "nirrcapcl", "hzdept_r", "hzdepb_r", "sandtotal_r", "silttotal_r", "claytotal_r", "om_r", "dbthirdbar_r",
              "awc_r", "ksat_r", "ph1to1h2o_r", "kwfact", "ec_r", "cec7_r"]
    top = ["1", "Test silt loam", "9", "Testus", "85", "B/D", "Well drained", "2", "5", "Mollisols", "2",
           "0", "20", "20", "60", "20", "4.0", "1.30", "0.22", "9", "6.5", ".32", "0", "20"]
    sub = top[:11] + ["20", "100", "20", "55", "25", "1.0", "1.40", "0.18", "9", "6.8", ".37", "0", "18"]

    def handler(req: httpx.Request) -> httpx.Response:
        if b"corestrictions" in req.content:
            return httpx.Response(200, json={"Table": [["resdept_r", "reskind"], ["80", "Fragipan"]]})
        return httpx.Response(200, json={"Table": [header, top, sub]})

    mock_http(handler)
    s = ssurgo.fetch_soil_profile(42.0, -93.7)
    assert s["series"] == "Testus" and s["texture_class"] == "silt loam"
    assert s["organic_matter_pct"] == pytest.approx((4.0 * 20 + 1.0 * 10) / 30, abs=0.01)  # depth-weighted
    assert s["hydrologic_group"] == "B" and s["kw_factor"] == 0.32
    assert s["root_zone_depth_cm"] == 80  # limited by the restrictive layer
    assert s["awc_profile_mm"] == pytest.approx(0.22 * 200 + 0.18 * 800, abs=1)


def test_ssurgo_outside_survey_area(mock_http):
    mock_http(lambda req: httpx.Response(200, json={}))
    with pytest.raises(base.ConnectorError):
        ssurgo.fetch_soil_profile(-25.0, 135.0)


def test_daymet_csv_parsing():
    text = "Latitude: 38\nHow to cite: x\nyear,yday,prcp (mm/day),tmax (deg c),tmin (deg c)\n2023,1,0.0,5.0,-3.0\n2023,32,12.5,8.0,-1.0\n"
    out = ground_truth.parse_daymet(text, "live")
    assert out["dates"] == ["20230101", "20230201"]
    assert out["series"]["precip"] == [0.0, 12.5]


def test_cdl_point_lookup_maps_classes_to_crops(mock_http):
    def handler(req: httpx.Request) -> httpx.Response:
        code, name = {"2022": (1, "Corn"), "2023": (5, "Soybeans")}[req.url.params["year"]]
        return httpx.Response(200, text=f'<r>{{x: 1, y: 2, value: {code}, category: "{name}", color: "#fff"}}</r>')

    mock_http(handler)
    out = cropland.cdl_history(42.0, -93.78, [2022, 2023])
    assert [y["crop_id"] for y in out["years"]] == ["corn", "soybean"]
    assert out["provenance"]["access"] == "live"


def test_keyed_sources_degrade_to_labelled_fallbacks():
    assert cropland.nass_county_yield("corn", "IA", "Story")["provenance"]["access"] == "unavailable"
    assert cropland.openet_monthly(36.3, -120.1, "2023-01-01", "2023-12-31")["provenance"]["access"] == "unavailable"


def test_gibs_catalogue_templates_are_complete():
    layers = gibs.catalogue()
    assert len(layers) >= 10
    for layer in layers:
        url = layer["tile_url"]
        assert layer["id"] in url and "{z}/{y}/{x}" in url and "{layer}" not in url and "{tms}" not in url
        assert ("{time}" in url) == (not (layer["temporal"] == "static" and not layer["start"]))


def test_albers_projection_matches_epsg_5070():
    x, y = geo.albers_conus(23.0, -96.0)  # projection origin
    assert abs(x) < 1 and abs(y) < 1
    east, _ = geo.albers_conus(40.0, -90.0)
    west, _ = geo.albers_conus(40.0, -102.0)
    assert east == pytest.approx(-west, rel=1e-9) and 480_000 < east < 540_000  # symmetric about the -96 meridian
    x, y = geo.albers_conus(42.0, -93.78)
    assert 150_000 < x < 220_000 and 2_050_000 < y < 2_170_000  # central Iowa in CONUS Albers metres


def test_texture_triangle():
    assert geo.usda_texture_class(20, 60, 20) == "silt loam"
    assert geo.usda_texture_class(90, 5, 5) == "sand"
    assert geo.usda_texture_class(20, 20, 60) == "clay"
    assert geo.usda_texture_class(40, 40, 20) == "loam"
