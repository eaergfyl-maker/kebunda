/**
 * API contract types. One-to-one with backend/app/models/schemas and docs/api-contracts.
 * If you need a field that is not typed here, add it here first (shared file: open a small PR).
 */

export type DimensionId = "water" | "soil" | "erosion" | "pest" | "income";
export const DIMENSIONS: DimensionId[] = ["water", "soil", "erosion", "pest", "income"];

export type Tillage = "conventional" | "reduced" | "no_till";
export type RiskTolerance = "low" | "medium" | "high";
export type Access = "live" | "cache" | "curated" | "proxy" | "unavailable" | "model";
export type HazardId = "storm" | "heat" | "frost" | "drought" | "leaching";
export type StrategyRole = "baseline" | "step" | "match" | "resilient" | "income" | "custom";
export type CropKind = "cash" | "cover" | "forage" | "perennial";

export type Priorities = Record<DimensionId, number>;

export interface Constraints {
  irrigation_available?: boolean;
  water_allocation_mm?: number;
  equipment?: string[];
  custom_hire_available?: boolean;
  livestock?: boolean;
  risk_tolerance?: RiskTolerance;
  tillage?: Tillage;
  allow_cover_crops?: boolean;
  allow_tillage_change?: boolean;
  allow_fallow?: boolean;
  max_rotation_years?: number;
  exclude_crops?: string[];
  must_include_crops?: string[];
  slope_pct?: number;
}

export interface Scenario {
  temp_delta_c: number;
  rain_pct: number;
  storm_intensity_pct: number;
  water_cap_pct: number;
}
export type ScenarioKey = keyof Scenario;

export interface RotationSpec {
  id?: string | null;
  role?: string | null;
  name?: string | null;
  /** One list of crop ids per rotation year. [] is a fallow year. */
  years: string[][];
  tillage?: Tillage | null;
}

export interface Provenance {
  source: string | null;
  dataset: string | null;
  access: Access | null;
  resolution_m: number | null;
  cadence: string | null;
  period: string | null;
  url: string | null;
  note: string | null;
  retrieved_at?: string | null;
}

// ---------------------------------------------------------------------------- farms

export interface FarmSummary {
  id: string;
  kind: "benchmark" | "custom";
  name: string;
  short_name: string;
  region: string;
  state: string | null;
  district: string | null;
  lat: number;
  lon: number;
  area_ha: number;
  headline: string;
  challenge_tags: string[];
  baseline_name: string;
  irrigation: string;
  annual_precip_mm: number;
  mean_annual_temp_c: number;
  soil_series: string | null;
  soil_texture: string | null;
  organic_matter_pct: number | null;
}

export interface FarmDefinition {
  id: string;
  name: string;
  short_name: string;
  region: string;
  state: string | null;
  district: string | null;
  lat: number;
  lon: number;
  area_ha: number;
  headline: string;
  story: string;
  challenge_tags: string[];
  management: {
    irrigation: { type: string; label: string; allocation_mm: number; sustainable_mm: number; efficiency: number; cost_per_mm_ha: number; source: string | null };
    tillage: Tillage;
    livestock: boolean;
    custom_hire_available: boolean;
    equipment: string[];
    tile_drained: boolean;
  };
  baseline_rotation: { name: string; years: string[][]; tillage: Tillage; note: string };
  baseline_assumed?: boolean;
  water_context: { aquifer: string | null; in_situ_trend_m_yr: number | null; in_situ_source: string | null; note: string };
  default_priorities: Priorities;
  sources: string[];
}

export interface SoilProfile {
  series: string;
  map_unit_name?: string | null;
  texture_class: string;
  sand_pct: number;
  silt_pct: number;
  clay_pct: number;
  organic_matter_pct: number;
  bulk_density_g_cm3: number;
  awc_cm_cm: number;
  ph: number;
  ec_ds_m: number;
  kw_factor: number;
  t_factor_tons_ac_yr: number;
  hydrologic_group: string;
  drainage_class: string;
  representative_slope_pct?: number | null;
  root_zone_depth_cm: number;
  generic?: boolean;
  provenance?: Provenance;
}

export interface Terrain {
  elevation_m: number;
  slope_pct: number;
  aspect_deg: number;
  relief_m: number;
  provenance: Provenance;
}

export interface Trend {
  per_decade: number;
  p_value: number;
  significant: boolean;
}

export interface ClimateMonthly {
  tmean: number[];
  tmax: number[];
  tmin: number[];
  precip: number[];
  precip_imerg: number[];
  et0: number[];
  wet_root: number[];
  wet_top: number[];
  solar: number[];
  rh: number[];
  vpd_kpa: number[];
  wet_days: number[];
  wet_day_mean_mm: number[];
  p95_daily_mm: number[];
  max_1day_mm: number[];
  erosive_days: number[];
  erosivity_share: number[];
  frost_days: number[];
  heat_days_32: number[];
  heat_days_35: number[];
}

export interface ClimateSummary {
  years: number[];
  monthly: ClimateMonthly;
  frost: {
    last_spring_frost_doy_median: number;
    last_spring_frost_doy_p90: number;
    first_fall_frost_doy_median: number;
    first_fall_frost_doy_p10: number;
    frost_free_days_median: number;
    frost_free_days_p10: number;
  };
  annual: Record<string, (number | null)[]>;
  trends: Record<string, Trend>;
  drought_months_per_year: number[];
  annual_precip_mm: number;
  annual_et0_mm: number;
  mean_annual_temp_c: number;
  aridity_index: number;
  provenance: Provenance;
}

/** A satellite product resampled to calendar months. by_year[y][m]. */
export interface MonthlyProduct {
  years: number[];
  monthly: (number | null)[];
  by_year: (number | null)[][];
  n_observations: number;
  provenance: Provenance | null;
}

export interface Fact {
  id: string;
  dimension: DimensionId;
  headline: string;
  detail: string;
  value: number | null;
  unit: string | null;
  trend: Trend | null;
  source: string | null;
  dataset: string | null;
  access: Access | null;
  resolution_m: number | null;
  period: string | null;
}

export interface LayerRow {
  id: string;
  variable: string;
  label: string;
  source: string | null;
  dataset: string | null;
  access: Access | null;
  native_resolution_m: number | null;
  cadence: string | null;
  period: string | null;
  url: string | null;
  note: string | null;
  pixel_to_field_ratio: number | null;
  pixels_inside_field: number | null;
  representativeness: number;
  completeness: number;
  confidence: number;
  harmonisation: string;
  used_for: string;
}

export interface DimensionConfidence {
  data: number;
  model: number;
  combined: number;
  label: "high" | "moderate" | "low";
}
export type ConfidenceReport = Record<DimensionId, DimensionConfidence> & { overall: number };

export interface PrecipSourceStats {
  correlation: number | null;
  bias_pct: number;
  rmse_mm_month: number;
  n_months: number;
}

export interface Fusion {
  precip: {
    monthly_mm: number[];
    relative_sigma: number[];
    annual_mm: number;
    annual_by_source: Record<string, number>;
    weights: Record<string, number>;
    measured_error: Record<string, number>;
    bias_vs_merra2: number[];
    method: string;
    has_ground: boolean;
  };
  precip_comparison: {
    monthly_normals: { merra2: (number | null)[]; imerg: (number | null)[]; ground: (number | null)[] | null };
    vs_ground: { merra2: PrecipSourceStats | null; imerg: PrecipSourceStats | null } | null;
    heavy_rain_days_per_year: Record<string, number | null>;
    recent_months: { year: number; month: number; merra2: number | null; imerg: number | null; ground: number | null }[];
    ground_provenance: Provenance | null;
  };
  soil_moisture: {
    volumetric: number[];
    plant_available_fraction: number[];
    plant_available_mm: number[];
    hydraulics: { wilting_point: number; field_capacity: number; saturation: number; available_water: number };
    method: string;
  };
  soil_moisture_source?: { kind: string; provenance: Provenance };
  layers: LayerRow[];
  confidence: ConfidenceReport;
  field_width_m: number;
  target_grid: string;
}

export interface HazardMonth {
  month: number;
  label: string;
  precip_mm: number;
  et0_mm: number;
  tmax_c: number;
  tmin_c: number;
  erosivity_share: number;
  storm_hazard: number;
  erosive_days: number;
  p95_daily_mm: number;
  heat_days_35: number;
  frost_days: number;
  root_zone_wetness: number;
  vpd_kpa: number;
  ndvi_observed: number | null;
  lst_observed_c: number | null;
}

export interface CropCycles {
  years: { year: number; cycles: number; peak_dates: string[] }[];
  cycles_per_year: number;
  peak_month_counts: number[];
  evergreen: boolean;
  provenance: Provenance;
}

export interface GaezCrop {
  gaez_crop: string;
  water_supply: string;
  si: number | null;
  class: string | null;
  si_2050s: number | null;
  class_2050s: string | null;
  change_2050s: number | null;
}

export interface FieldOverview {
  id: string;
  kind: "benchmark" | "custom";
  farm: FarmDefinition;
  soil: SoilProfile;
  terrain: Terrain | null;
  climate: ClimateSummary;
  series: {
    years: number[];
    precip: (number | null)[][];
    wet_root: (number | null)[][];
    wet_root_z: (number | null)[][];
    heat_days_35: (number | null)[][];
    tmax: (number | null)[][];
    erosivity: (number | null)[][];
  };
  vegetation: MonthlyProduct | null;
  surface_temperature: MonthlyProduct | null;
  evapotranspiration: MonthlyProduct | null;
  groundwater: {
    region: string | null;
    tws_trend_cm_yr: number | null;
    uncertainty_cm_yr: number | null;
    driver?: string;
    provenance: Provenance;
    local: FarmDefinition["water_context"];
  };
  crop_history: CropCycles | null;
  ndvi_series?: { dates: string[]; values: number[] } | null;
  gaez?: { crops: Record<string, GaezCrop>; provenance: Provenance } | null;
  fusion: Fusion;
  hazards: { months: HazardMonth[] };
  insights: { facts: Fact[]; signals: Record<string, unknown>; period: string };
  issues: { layer: string; problem: string }[];
  disclaimer: string;
}

// ------------------------------------------------------------------------ strategies

export interface Phase {
  crop_id: string;
  crop_name: string;
  kind: CropKind;
  year_index: number;
  /** Month index on the rotation timeline, 0 .. n_years*12-1. */
  plant_month: number;
  end_month: number;
  plant_calendar_month: number;
  end_calendar_month: number;
  duration_months: number;
  wraps: boolean;
  delay_months: number;
  biomass_frac: number | null;
  winterkills: boolean;
  issues: string[];
}

export interface MonthCell {
  index: number;
  calendar_month: number;
  year_index: number;
  crop_id: string | null;
  kind: CropKind | null;
  cover: number;
  canopy: number;
  residue_cover: number;
  green: number;
  bare: boolean;
  runoff_mm: number;
  drainage_mm: number;
  transpiration_mm: number;
  demand_mm: number;
  soil_evap_mm: number;
  irrigation_mm: number;
  soil_water_frac: number;
  erosion_t_ha: number;
  n_leach_kg_ha: number;
}

export interface Metrics {
  irrigation_mm_yr: number;
  allocation_used_pct: number | null;
  crop_water_use_mm_yr: number;
  transpiration_mm_yr: number;
  soil_evaporation_mm_yr: number;
  runoff_mm_yr: number;
  deep_drainage_mm_yr: number;
  water_stress_pct: number;
  infiltration_pct: number;
  productive_water_pct: number;
  soil_loss_t_ha_yr: number;
  soil_loss_tons_ac_yr: number;
  soil_loss_vs_tolerable: number;
  bare_months_per_year: number;
  mean_ground_cover_pct: number;
  storm_exposure_pct: number;
  living_root_months_per_year: number;
  carbon_input_t_ha_yr: number;
  soc_change_t_ha_yr: number;
  om_change_pct_points_10yr: number;
  n_fertilizer_kg_ha_yr: number;
  n_legume_credit_kg_ha_yr: number;
  n_self_sufficiency_pct: number;
  n_leaching_kg_ha_yr: number;
  legume_years: number;
  pest_break_score: number;
  distinct_cash_crops: number;
  net_return_per_ha_yr: number;
  gross_revenue_per_ha_yr: number;
  cost_per_ha_yr: number;
  price_sd_per_ha: number;
  market_access: number;
  forage_value: number;
  net_per_mm_irrigation: number | null;
}

export type Scores = Record<DimensionId, number>;

export interface Fit {
  fit: number;
  weighted_score: number;
  penalties: { reason: string; points: number }[];
  weights: Record<DimensionId, number>;
  change: { new_crops: string[]; adds_cover_crops: boolean; tillage_change: boolean; equipment_needed: string[]; load: number };
}

export interface History {
  years: number[];
  net_per_ha: number[];
  irrigation_mm: number[];
  water_stress_pct: number[];
  mean_net_per_ha: number;
  weather_sd_per_ha: number;
  total_sd_per_ha: number;
  bad_year_net_per_ha: number;
  worst_years: number[];
  variability_ratio: number;
}

export interface Reason {
  driver: "priority" | "co-benefit" | "climate" | "soil" | "pest" | "market" | "reference" | "strength" | "strain";
  text: string;
  dimension?: DimensionId;
}

export interface EvidenceItem {
  kind: "observed" | "modelled";
  id: string;
  source: string | null;
  dataset: string | null;
  access: Access | null;
  statement: string;
  detail: string;
  value: number | null;
  unit: string | null;
  dimension: DimensionId;
}

export interface BenefitItem {
  metric: string;
  label: string;
  unit: string;
  dimension: DimensionId;
  meaning: string;
  baseline: number;
  value: number;
  delta: number;
  delta_pct: number | null;
  direction: "better" | "worse" | "same";
  confidence: "high" | "moderate" | "low";
  range: [number, number] | null;
}

export interface GapItem {
  id: string;
  kind: "data" | "resolution" | "model" | "validation" | "blind_spot";
  severity: "low" | "medium" | "high" | "standing";
  topic: string;
  detail: string;
  close_by: string;
}

export interface RiskItem {
  id: string;
  category: string;
  title: string;
  detail: string;
  who: string[];
  severity: "check" | "caution" | "critical";
}

/** The five things every strategy must explain. */
export interface Explanation {
  why: Reason[];
  evidence: EvidenceItem[];
  benefits: { items: BenefitItem[]; improves: number; trade_offs: number; summary: string };
  gaps: {
    items: GapItem[];
    confidence: Record<DimensionId, DimensionConfidence>;
    overall_confidence: number;
    score_uncertainty: Record<DimensionId, number>;
    statement: string;
  };
  risks: RiskItem[];
}

export interface VulnerabilityCell {
  index: number;
  year_index: number;
  calendar_month: number;
  label: string;
  crop_id: string | null;
  crop_name: string | null;
  kind: CropKind | null;
  cover: number;
  canopy: number;
  residue_cover: number;
  green: number;
  bare: boolean;
  risks: Record<HazardId, number>;
  top_risk: HazardId | null;
  soil_water_frac: number;
  erosion_t_ha: number;
}

export interface VulnerabilityWindow {
  hazard: HazardId;
  label: string;
  months: string;
  month_count_per_year: number;
  peak: number;
  crops: string[];
}

export interface Vulnerability {
  cells: VulnerabilityCell[];
  summary: {
    bare_months_per_year: number;
    bare_calendar_months: number[];
    bare_label: string;
    erosive_rain_on_bare_soil_pct: number;
    mean_risk: Record<HazardId, number>;
    windows: VulnerabilityWindow[];
    headline: string;
  };
}

export interface CalendarValidation {
  modelled_green: number[];
  modelled_cover: number[];
  observed_ndvi: (number | null)[];
  correlation: number | null;
  observed_low_months: number[];
  modelled_low_months: number[];
  agreement: "strong" | "fair" | "weak";
  explanation: string;
}

export interface EconomicsRow {
  crop_id: string;
  crop_name: string;
  kind: CropKind;
  yield: number | null;
  yield_unit: string | null;
  relative_yield: number | null;
  yield_factors?: Record<string, number>;
  revenue: number;
  cost: number;
  net: number;
  n_applied_kg_ha: number;
  irrigation_mm: number;
  local_reference?: boolean;
}

export interface YearLabel {
  year: number;
  fallow: boolean;
  crops: { id: string; name: string; role: string; family: string; functional_group: string; legume: boolean }[];
}

export interface Strategy {
  id: string;
  role: StrategyRole;
  rank: number;
  title: string;
  tagline: string;
  name: string;
  years: string[][];
  year_labels: YearLabel[];
  tillage: Tillage;
  tillage_label: string;
  n_years: number;
  feasible: boolean;
  issues: string[];
  phases: Phase[];
  months: MonthCell[];
  metrics: Metrics;
  scores: Scores;
  fit: Fit;
  history: History | null;
  pests: {
    score: number;
    host_break_ratio: number;
    functional_groups: string[];
    short_breaks: { group: string; crop_id: string; crop_name: string; interval_years: number; recommended_years: number; named_pests: string[] }[];
    green_bridges: { cover: string; next_crop: string; group: string }[];
    distinct_cash_crops: number;
  };
  economics: EconomicsRow[];
  market: { score: number; rows: { crop_id: string; crop_name: string; access: number; verified_locally: boolean; note: string }[] };
  equipment_needed: string[];
  headline_numbers: { label: string; value: number; unit: string; baseline: number; higher_is_better: boolean }[];
  vulnerability: Vulnerability;
  explanation: Explanation;
  calendar_validation?: CalendarValidation | null;
}

export interface CompareRequest {
  field_id: string;
  priorities?: Partial<Priorities>;
  constraints?: Constraints;
  scenario?: Scenario;
  baseline?: RotationSpec;
  custom_strategies?: RotationSpec[];
}

export interface CompareResponse {
  field_id: string;
  field_name: string;
  priorities: Priorities;
  priority_labels: Record<DimensionId, string>;
  constraints: Constraints;
  scenario: Scenario;
  scenario_active: boolean;
  baseline_note: string | null;
  baseline_assumed: boolean;
  strategies: Strategy[];
  ranking: string[];
  summary: { top_id: string; statement: string; tied_ids: string[]; baseline_fit: number };
  search: { crops_considered: string[]; rotations_screened: number; rotations_simulated: number };
  confidence: ConfidenceReport;
  disclaimer: string;
}

// -------------------------------------------------------------------------- scenarios

export interface TodayVsScenario {
  today: number;
  scenario: number;
  delta: number;
}

export interface ScenarioLimit {
  min: number;
  max: number;
  step: number;
  unit: string;
  label: string;
  plain: string;
}

export interface ScenarioPreset {
  id: string;
  label: string;
  description: string;
  scenario: Scenario;
}

export interface StressRow {
  id: string | null;
  role: string | null;
  name: string;
  years: string[][];
  tillage: Tillage;
  feasible: boolean;
  fit: TodayVsScenario;
  scores: Record<DimensionId, TodayVsScenario>;
  metrics: Record<string, TodayVsScenario>;
  bad_year_net_per_ha: { today: number; scenario: number } | null;
  yields: { crop_id: string; crop_name: string; today: number; scenario: number; unit: string; change_pct: number; limiting: string | null }[];
  flags: string[];
  net_retained_pct: number | null;
  phases: Phase[];
}

export interface StressTestResponse {
  field_id: string;
  scenario: Scenario;
  limits: Record<ScenarioKey, ScenarioLimit>;
  climate_shift: Record<string, { today: number | null; scenario: number | null; delta: number | null }>;
  strategies: StressRow[];
  ranking_today: (string | null)[];
  ranking_scenario: (string | null)[];
  ranking_changed: boolean;
  verdict: string;
  note: string;
  disclaimer: string;
}

export interface SweepResponse {
  field_id: string;
  parameter: ScenarioKey;
  label: string;
  unit: string;
  values: number[];
  series: { id: string | null; name: string; fit: number[]; net: number[]; feasible: boolean[] }[];
  crossings: { between: [number, number]; from: string; to: string }[];
}

// -------------------------------------------------------------------- reference data

export interface GibsLayerMeta {
  id: string;
  title: string;
  group: "imagery" | "vegetation" | "water" | "heat" | "terrain" | "landscape";
  mission: string;
  tms: string;
  ext: string;
  temporal: "daily" | "monthly" | "yearly" | "static";
  start: string | null;
  end: string | null;
  max_zoom: number;
  resolution_m: number;
  plain: string;
  legend: { unit: string; stops: [number, string][] } | null;
  tile_url: string;
  attribution: string;
}

export interface CropCatalogEntry {
  id: string;
  name: string;
  family: string;
  functional_group: string;
  legume: boolean;
  role: "cash" | "cover" | "forage";
  cycle: "spring" | "winter" | "perennial";
  root_depth_m: number;
  deep_rooted: boolean;
  drought_tolerance: number;
  kc_mid: number;
  n_demand_kg_ha: number;
  n_credit_kg_ha: number;
  equipment: string[];
  benefits: string[];
  cautions: string[];
  named_pests: string[];
}

export interface CropCatalog {
  version: string;
  crops: CropCatalogEntry[];
  equipment_labels: Record<string, string>;
  tillage_systems: { id: Tillage; label: string }[];
  sources: string[];
  note: string;
}

export interface SuitabilityRow {
  crop_id: string;
  name: string;
  family: string;
  role: string;
  feasible: boolean;
  suitability: number;
  suitability_class: string;
  limiting_factors: string[];
  reasons: string[];
  net_return_per_ha: number | null;
  irrigation_mm: number;
  water_use_mm: number;
  plant_month: number | null;
  harvest_month: number | null;
  market_access: number;
  market_verified: boolean;
  has_local_yield: boolean;
  equipment_missing: string[];
  legume: boolean;
  deep_rooted: boolean;
}

export interface RotationOptions {
  dimensions: { id: DimensionId; label: string; help: string }[];
  priority_presets: { id: string; label: string; description: string; priorities: Priorities }[];
  tillage_systems: { id: Tillage; label: string }[];
  risk_tolerance: { id: RiskTolerance; label: string; help: string }[];
  equipment: { id: string; label: string }[];
  crops: { id: string; name: string; role: "cash" | "cover" | "forage"; family: string; cycle: string; functional_group: string; legume: boolean }[];
}

export interface DataSource {
  id: string;
  name: string;
  agency: string;
  group: string;
  status: "live" | "key" | "curated" | "proxy" | "map" | "planned";
  use: string;
  url: string;
}

export interface PowerPoint {
  lat: number;
  lon: number;
  grid_elevation_m: number | null;
  annual_precip_mm: number;
  annual_et0_mm: number;
  mean_annual_temp_c: number;
  aridity_index: number;
  frost: ClimateSummary["frost"];
  monthly: ClimateMonthly;
  trends: Record<string, Trend>;
  headline: string;
  provenance: Provenance;
}

export interface VulnerabilityResponse {
  field_id: string;
  hazards: { months: HazardMonth[] };
  hazard_labels: Record<HazardId, string>;
  baseline: { name: string; years: string[][]; tillage: Tillage; phases: Phase[]; calendar: Vulnerability };
  validation: CalendarValidation | null;
  disclaimer: string;
}

export interface ApiErrorBody {
  error: string;
  detail: string;
  hint: string | null;
}
