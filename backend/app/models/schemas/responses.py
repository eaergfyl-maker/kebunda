"""Response models. They validate what the engines return and generate the OpenAPI contract.

Leaf blocks that are wide tables of numbers (monthly climate grids, layer inventories) are
typed as dictionaries here and documented field by field in docs/api-contracts/API.md.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class Loose(BaseModel):
    model_config = ConfigDict(extra="allow")


class Provenance(Loose):
    source: str | None = None
    dataset: str | None = None
    access: str | None = None  # live | cache | curated | proxy | unavailable | model
    resolution_m: float | None = None
    cadence: str | None = None
    period: str | None = None
    url: str | None = None
    note: str | None = None
    retrieved_at: str | None = None


class FarmSummary(Loose):
    id: str
    kind: str
    name: str
    short_name: str
    region: str
    state: str | None
    county: str | None
    lat: float
    lon: float
    area_ha: float
    headline: str
    challenge_tags: list[str]
    baseline_name: str
    irrigation: str
    annual_precip_mm: float
    mean_annual_temp_c: float
    soil_series: str | None
    soil_texture: str | None
    organic_matter_pct: float | None


class Fact(Loose):
    id: str
    dimension: str
    headline: str
    detail: str
    value: float | None = None
    unit: str | None = None
    source: str | None = None
    dataset: str | None = None
    access: str | None = None


class Insights(Loose):
    facts: list[Fact]
    signals: dict[str, Any]
    period: str


class LayerRow(Loose):
    id: str
    variable: str
    label: str
    source: str | None
    access: str | None
    native_resolution_m: float | None
    pixel_to_field_ratio: float | None
    representativeness: float
    completeness: float
    confidence: float
    harmonisation: str
    used_for: str


class DimensionConfidence(Loose):
    data: float
    model: float
    combined: float
    label: str


class Fusion(Loose):
    precip: dict[str, Any]
    precip_comparison: dict[str, Any]
    soil_moisture: dict[str, Any]
    layers: list[LayerRow]
    confidence: dict[str, Any]
    field_width_m: float
    target_grid: str


class FieldOverview(Loose):
    id: str
    kind: str
    farm: dict[str, Any]
    soil: dict[str, Any]
    terrain: dict[str, Any] | None
    climate: dict[str, Any]
    series: dict[str, Any]
    vegetation: dict[str, Any] | None
    surface_temperature: dict[str, Any] | None
    evapotranspiration: dict[str, Any] | None
    groundwater: dict[str, Any]
    crop_history: dict[str, Any] | None
    fusion: Fusion
    hazards: dict[str, Any]
    insights: Insights
    issues: list[dict[str, Any]]
    disclaimer: str


# ------------------------------------------------------------------ rotation strategies


class Phase(Loose):
    crop_id: str
    crop_name: str
    kind: str  # cash | cover | forage | perennial
    year_index: int
    plant_month: int
    end_month: int
    plant_calendar_month: int
    end_calendar_month: int
    duration_months: int
    wraps: bool
    delay_months: int
    biomass_frac: float | None
    winterkills: bool
    issues: list[str]


class MonthCell(Loose):
    index: int
    calendar_month: int
    year_index: int
    crop_id: str | None
    kind: str | None
    cover: float
    canopy: float
    residue_cover: float
    green: float
    bare: bool
    runoff_mm: float
    drainage_mm: float
    transpiration_mm: float
    demand_mm: float
    soil_evap_mm: float
    irrigation_mm: float
    soil_water_frac: float
    erosion_t_ha: float
    n_leach_kg_ha: float


class Metrics(Loose):
    irrigation_mm_yr: float
    allocation_used_pct: float | None
    crop_water_use_mm_yr: float
    water_stress_pct: float
    infiltration_pct: float
    productive_water_pct: float
    runoff_mm_yr: float
    deep_drainage_mm_yr: float
    soil_loss_t_ha_yr: float
    soil_loss_tons_ac_yr: float
    soil_loss_vs_tolerable: float
    bare_months_per_year: float
    mean_ground_cover_pct: float
    storm_exposure_pct: float
    living_root_months_per_year: float
    carbon_input_t_ha_yr: float
    soc_change_t_ha_yr: float
    om_change_pct_points_10yr: float
    n_fertilizer_kg_ha_yr: float
    n_legume_credit_kg_ha_yr: float
    n_self_sufficiency_pct: float
    n_leaching_kg_ha_yr: float
    pest_break_score: float
    distinct_cash_crops: int
    net_return_per_acre_yr: float
    gross_revenue_per_acre_yr: float
    cost_per_acre_yr: float
    market_access: float
    forage_value: float


class Scores(BaseModel):
    water: float
    soil: float
    erosion: float
    pest: float
    income: float


class Fit(Loose):
    fit: float
    weighted_score: float
    penalties: list[dict[str, Any]]
    weights: dict[str, float]
    change: dict[str, Any]


class History(Loose):
    years: list[int]
    net_per_acre: list[float]
    irrigation_mm: list[float]
    water_stress_pct: list[float]
    mean_net_per_acre: float
    weather_sd_per_acre: float
    total_sd_per_acre: float
    bad_year_net_per_acre: float
    worst_years: list[int]
    variability_ratio: float


class Reason(Loose):
    driver: str
    text: str
    dimension: str | None = None


class EvidenceItem(Loose):
    kind: str  # observed | modelled
    id: str
    source: str | None
    dataset: str | None
    access: str | None
    statement: str
    detail: str
    dimension: str


class BenefitItem(Loose):
    metric: str
    label: str
    unit: str
    dimension: str
    meaning: str
    baseline: float
    value: float
    delta: float
    delta_pct: float | None
    direction: str  # better | worse | same
    confidence: str
    range: list[float] | None


class Benefits(BaseModel):
    items: list[BenefitItem]
    improves: int
    trade_offs: int
    summary: str


class GapItem(Loose):
    id: str
    kind: str  # data | resolution | model | validation | blind_spot
    severity: str
    topic: str
    detail: str
    close_by: str


class Gaps(Loose):
    items: list[GapItem]
    confidence: dict[str, DimensionConfidence]
    overall_confidence: float
    score_uncertainty: dict[str, float]
    statement: str


class RiskItem(Loose):
    id: str
    category: str
    title: str
    detail: str
    who: list[str]
    severity: str  # check | caution | critical


class Explanation(BaseModel):
    why: list[Reason]
    evidence: list[EvidenceItem]
    benefits: Benefits
    gaps: Gaps
    risks: list[RiskItem]


class VulnerabilityCell(Loose):
    index: int
    year_index: int
    calendar_month: int
    label: str
    crop_id: str | None
    crop_name: str | None
    kind: str | None
    cover: float
    bare: bool
    risks: dict[str, float]
    top_risk: str | None


class Vulnerability(Loose):
    cells: list[VulnerabilityCell]
    summary: dict[str, Any]


class Strategy(Loose):
    id: str
    role: str  # baseline | step | match | resilient | income | custom
    rank: int
    title: str
    tagline: str
    name: str
    years: list[list[str]]
    year_labels: list[dict[str, Any]]
    tillage: str
    tillage_label: str
    n_years: int
    feasible: bool
    issues: list[str]
    phases: list[Phase]
    months: list[MonthCell]
    metrics: Metrics
    scores: Scores
    fit: Fit
    history: History | None = None
    pests: dict[str, Any]
    economics: list[dict[str, Any]]
    market: dict[str, Any]
    equipment_needed: list[str]
    headline_numbers: list[dict[str, Any]]
    vulnerability: Vulnerability
    explanation: Explanation
    calendar_validation: dict[str, Any] | None = None


class CompareResponse(Loose):
    field_id: str
    field_name: str
    priorities: dict[str, float]
    priority_labels: dict[str, str]
    constraints: dict[str, Any]
    scenario: dict[str, float]
    scenario_active: bool
    baseline_note: str | None
    baseline_assumed: bool
    strategies: list[Strategy]
    ranking: list[str]
    summary: dict[str, Any]
    search: dict[str, Any]
    confidence: dict[str, Any]
    disclaimer: str


class StressRow(Loose):
    id: str | None
    role: str | None
    name: str
    years: list[list[str]]
    tillage: str
    feasible: bool
    fit: dict[str, float]
    scores: dict[str, dict[str, float]]
    metrics: dict[str, dict[str, float]]
    yields: list[dict[str, Any]]
    flags: list[str]
    net_retained_pct: float | None


class StressTestResponse(Loose):
    field_id: str
    scenario: dict[str, float]
    limits: dict[str, Any]
    climate_shift: dict[str, Any]
    strategies: list[StressRow]
    ranking_today: list[str | None]
    ranking_scenario: list[str | None]
    ranking_changed: bool
    verdict: str
    note: str
    disclaimer: str


class SweepResponse(Loose):
    field_id: str
    parameter: str
    label: str
    unit: str
    values: list[float]
    series: list[dict[str, Any]]
    crossings: list[dict[str, Any]]


class ErrorResponse(BaseModel):
    error: str
    detail: str
    hint: str | None = None
