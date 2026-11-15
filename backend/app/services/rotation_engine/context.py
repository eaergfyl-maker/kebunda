"""FieldContext: everything the agronomy models need about one field, in one place.

It is built from the fused observations plus the farmer's constraints and (optionally) a
climate scenario, so the very same models run for the baseline climate and for a
"what-if" stress test.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache

from app.config import settings
from app.utils.geo import DAYS_IN_MONTH, MID_MONTH_DOY, hargreaves_et0_mm_day, ls_factor

NEUTRAL_SCENARIO = {"temp_delta_c": 0.0, "rain_pct": 0.0, "storm_intensity_pct": 0.0, "water_cap_pct": 100.0}

# Used only when SoilGrids has nothing for the coordinate (masked pixel or no answer). Flagged low-confidence.
GENERIC_SOIL = {
    "series": "Generic loam (no soil data found)", "texture_class": "loam", "sand_pct": 40.0, "silt_pct": 40.0,
    "clay_pct": 20.0, "organic_matter_pct": 2.5, "bulk_density_g_cm3": 1.4, "awc_cm_cm": 0.16, "ph": 6.8,
    "ec_ds_m": 0.0, "kw_factor": 0.32, "t_factor_tons_ac_yr": 5.0, "hydrologic_group": "B",
    "drainage_class": "Well drained", "root_zone_depth_cm": 120.0, "generic": True,
}


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    return json.loads((settings.data_dir / "crop-catalog" / "crops.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def crops_by_id() -> dict[str, dict]:
    return {c["id"]: c for c in load_catalog()["crops"]}


@dataclass
class Climate:
    lat: float
    tmean: list[float]
    tmax: list[float]
    tmin: list[float]
    tmax_sd: list[float]
    tmin_sd: list[float]
    precip: list[float]
    et0: list[float]
    wet_days: list[float]
    wet_day_mean: list[float]
    erosivity_share: list[float]
    r_factor: float  # MJ mm ha-1 h-1 yr-1
    tmax_base: list[float] = field(default_factory=list)  # today's normals, before any scenario shift
    years: list[int] = field(default_factory=list)
    hist_precip: list[list[float]] = field(default_factory=list)
    hist_tmax: list[list[float]] = field(default_factory=list)
    hist_tmin: list[list[float]] = field(default_factory=list)

    def month(self, m: int, year_index: int | None = None) -> tuple[float, float, float, float]:
        """(precip, tmax, tmin, et0) for calendar month m, from normals or one historical year."""
        if year_index is None:
            return self.precip[m], self.tmax[m], self.tmin[m], self.et0[m]
        p, tx, tn = self.hist_precip[year_index][m], self.hist_tmax[year_index][m], self.hist_tmin[year_index][m]
        return p, tx, tn, hargreaves_et0_mm_day(self.lat, MID_MONTH_DOY[m], tx, tn) * DAYS_IN_MONTH[m]


def rainfall_erosivity(annual_precip_mm: float, method: str = "rusle") -> float:
    """Annual R factor in SI units (MJ mm ha-1 h-1 yr-1).

    rusle     Renard & Freimund (1994) regressions on annual precipitation.
    req_nwrr  NRCS "equivalent R" for the Northwestern Wheat and Range Region, where most
              erosion comes from rain and snowmelt on thawing soil, not from intense storms.
    """
    p = max(1.0, annual_precip_mm)
    if method == "req_nwrr":
        return max(100.0, (-48.4 + 7.78 * p / 25.4) * 17.02)
    if p <= 850:
        return 0.0483 * p**1.610
    return 587.8 - 1.219 * p + 0.004105 * p**2


def build_climate(clim: dict, lat: float, scenario: dict | None = None, precip_bias: list[float] | None = None,
                  erosivity_method: str = "rusle") -> Climate:
    """Apply an optional scenario to the harmonised climate summary.

    temp_delta_c         shifts every month's Tmax/Tmin; reference ET, growing degree days,
                         frost days and heat days all respond through the same physics.
    rain_pct             scales rainfall totals (storm count unchanged, each storm bigger/smaller).
    storm_intensity_pct  same total, but falling in fewer, heavier events (more runoff, more erosive).
    """
    sc = {**NEUTRAL_SCENARIO, **(scenario or {})}
    dt = float(sc["temp_delta_c"])
    rain = 1.0 + float(sc["rain_pct"]) / 100.0
    storm = 1.0 + float(sc["storm_intensity_pct"]) / 100.0
    mo = clim["monthly"]
    bias = precip_bias or [1.0] * 12

    tmax = [t + dt for t in mo["tmax"]]
    tmin = [t + dt for t in mo["tmin"]]
    precip = [p * b * rain for p, b in zip(mo["precip"], bias)]
    et0 = [hargreaves_et0_mm_day(lat, MID_MONTH_DOY[m], tmax[m], tmin[m]) * DAYS_IN_MONTH[m] for m in range(12)]
    r = rainfall_erosivity(sum(precip), erosivity_method) * storm**0.81

    def fill(grid: list[list[float | None]], normals: list[float], scale: float = 1.0, add: float = 0.0, b=None):
        return [[(normals[m] if v is None else v) * scale * (b[m] if b else 1.0) + add for m, v in enumerate(row)] for row in grid]

    by = clim.get("by_year", {})
    return Climate(
        lat=lat,
        tmean=[(a + c) / 2 for a, c in zip(tmax, tmin)], tmax=tmax, tmin=tmin,
        tmax_sd=mo["tmax_sd"], tmin_sd=mo["tmin_sd"],
        precip=precip, et0=et0,
        wet_days=[max(0.3, w / storm) for w in mo["wet_days"]],
        wet_day_mean=[max(1.0, w * rain * storm) for w in mo["wet_day_mean_mm"]],
        erosivity_share=mo["erosivity_share"],
        r_factor=r,
        tmax_base=list(mo["tmax"]),
        years=clim.get("years", []),
        hist_precip=fill(by.get("precip", []), mo["precip"], rain, 0.0, bias),
        hist_tmax=fill(by.get("tmax", []), mo["tmax"], 1.0, dt),
        hist_tmin=fill(by.get("tmin", []), mo["tmin"], 1.0, dt),
    )


@dataclass
class FieldContext:
    farm: dict
    soil: dict
    climate: Climate
    slope_pct: float
    slope_length_m: float
    irrigated: bool
    allocation_mm: float
    irrigation_efficiency: float
    irrigation_cost_per_mm_ha: float
    tile_drained: bool
    equipment: set[str]
    custom_hire: bool
    livestock: bool
    reference_yields: dict
    local_market: dict
    scenario: dict
    data_confidence: float = 0.7
    gaez: dict = field(default_factory=dict)  # FAO GAEZ suitability per crop id for the field's grid cell

    # ---- derived soil hydraulics -------------------------------------------------
    @property
    def profile_depth_cm(self) -> float:
        return float(min(200.0, max(40.0, self.soil.get("root_zone_depth_cm") or 120.0)))

    @property
    def taw_profile_mm(self) -> float:
        """Plant-available water the whole root zone can hold."""
        return float(self.soil.get("awc_cm_cm") or 0.16) * self.profile_depth_cm * 10.0

    @property
    def soc_stock_t_ha(self) -> float:
        """Soil organic carbon in the top 30 cm (t C/ha); OM is ~58% carbon."""
        return float(self.soil["organic_matter_pct"]) / 1.724 / 100.0 * float(self.soil["bulk_density_g_cm3"]) * 30.0 * 100.0

    @property
    def k_si(self) -> float:
        return float(self.soil.get("kw_factor") or 0.32) * 0.1317

    @property
    def ls(self) -> float:
        return ls_factor(self.slope_pct, self.slope_length_m)

    @property
    def t_factor_t_ha(self) -> float:
        return float(self.soil.get("t_factor_tons_ac_yr") or 5.0) * 2.2417

    @property
    def lat(self) -> float:
        return self.climate.lat


def build_context(farm: dict, obs: dict, soil: dict | None, *, scenario: dict | None = None,
                  constraints: dict | None = None, precip_bias: list[float] | None = None,
                  data_confidence: float = 0.7) -> FieldContext:
    """Merge farm definition, observations, soil and farmer-entered constraints."""
    c = constraints or {}
    sc = {**NEUTRAL_SCENARIO, **(scenario or {})}
    mgmt = farm.get("management", {})
    irr = mgmt.get("irrigation") or {}
    irrigated = c.get("irrigation_available", irr.get("type", "none") != "none")
    allocation = float(c.get("water_allocation_mm", irr.get("allocation_mm") or (400.0 if irrigated else 0.0)))
    allocation *= float(sc["water_cap_pct"]) / 100.0
    terrain = obs.get("terrain") or {}
    soil_slope = (soil or {}).get("representative_slope_pct")
    # SRTM carries 1-2 m of vertical noise, which reads as a false 1-2% slope on flat land.
    # The soil survey's representative slope is a field value, so it leads; SRTM only adds
    # information where the relief it sees is clearly above its noise.
    srtm_slope = terrain.get("slope_pct") if (terrain.get("relief_m") or 0) > 4.0 else None
    if c.get("slope_pct"):
        slope = c["slope_pct"]
    elif soil_slope is not None and srtm_slope is not None:
        slope = 0.6 * soil_slope + 0.4 * srtm_slope
    elif soil_slope is not None:
        slope = soil_slope
    else:
        slope = srtm_slope if srtm_slope is not None else (terrain.get("slope_pct") or 2.0)
    equipment = set(c["equipment"]) if c.get("equipment") is not None else set(mgmt.get("equipment", []))
    return FieldContext(
        farm=farm,
        soil=soil or dict(GENERIC_SOIL),
        climate=build_climate(obs["climate"], farm["lat"], sc, precip_bias, mgmt.get("erosivity_method", "rusle")),
        slope_pct=max(0.1, float(slope)),
        slope_length_m=float(mgmt.get("slope_length_m", 80.0)),
        irrigated=bool(irrigated) and allocation > 0,
        allocation_mm=allocation if irrigated else 0.0,
        irrigation_efficiency=float(irr.get("efficiency") or 0.8),
        irrigation_cost_per_mm_ha=float(irr.get("cost_per_mm_ha") or 1.0),
        tile_drained=bool(mgmt.get("tile_drained", False)),
        equipment=equipment,
        custom_hire=bool(c.get("custom_hire_available", mgmt.get("custom_hire_available", True))),
        livestock=bool(c.get("livestock", mgmt.get("livestock", False))),
        reference_yields=farm.get("reference_yields", {}),
        local_market=farm.get("local_market", {}),
        scenario=sc,
        data_confidence=data_confidence,
        gaez=(obs.get("gaez") or {}).get("crops") or {},
    )
