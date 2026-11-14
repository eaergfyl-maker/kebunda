"""Request bodies. These are the contract the frontend types mirror (frontend/src/types/api.ts)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Tillage = Literal["conventional", "reduced", "no_till"]
RiskTolerance = Literal["low", "medium", "high"]


class Priorities(BaseModel):
    """How much each goal matters to the farmer, 0 (ignore) to 10 (critical)."""

    model_config = ConfigDict(extra="forbid")
    water: float | None = Field(None, ge=0, le=10, description="Save water and ride out drought")
    soil: float | None = Field(None, ge=0, le=10, description="Build organic matter and nitrogen")
    erosion: float | None = Field(None, ge=0, le=10, description="Keep soil covered and in place")
    pest: float | None = Field(None, ge=0, le=10, description="Break pest, weed and disease cycles")
    income: float | None = Field(None, ge=0, le=10, description="Income, forage and markets")

    def clean(self) -> dict:
        return {k: v for k, v in self.model_dump().items() if v is not None}


class Constraints(BaseModel):
    """What the farm can and cannot do. Every field is optional; omitted fields use the field's own defaults."""

    model_config = ConfigDict(extra="forbid")
    irrigation_available: bool | None = Field(None, description="False forces a rainfed evaluation")
    water_allocation_mm: float | None = Field(None, ge=0, le=2000, description="Irrigation water available per year (mm)")
    equipment: list[str] | None = Field(None, description="Equipment ids on the farm (see /rotations/options)")
    custom_hire_available: bool | None = Field(None, description="Can missing equipment be hired in?")
    livestock: bool | None = Field(None, description="Cattle or sheep available to graze covers and use forage")
    risk_tolerance: RiskTolerance | None = Field(None, description="low penalises new crops and thin markets harder")
    tillage: Tillage | None = Field(None, description="Overrides the baseline tillage system")
    allow_cover_crops: bool | None = None
    allow_tillage_change: bool | None = None
    allow_fallow: bool | None = None
    max_rotation_years: int | None = Field(None, ge=2, le=5)
    exclude_crops: list[str] | None = Field(None, description="Crop ids the farmer will not grow")
    must_include_crops: list[str] | None = Field(None, description="Crop ids to add to the search pool")
    slope_pct: float | None = Field(None, ge=0, le=60, description="Field slope if the farmer knows it")

    def clean(self) -> dict:
        return {k: v for k, v in self.model_dump().items() if v is not None}


class Scenario(BaseModel):
    """A what-if climate and water shift applied to the 2001-2024 record."""

    model_config = ConfigDict(extra="forbid")
    temp_delta_c: float = Field(0.0, ge=-1, le=5, description="Added to every month's temperature (deg C)")
    rain_pct: float = Field(0.0, ge=-50, le=30, description="Change in yearly precipitation (%)")
    storm_intensity_pct: float = Field(0.0, ge=0, le=60, description="Rain concentrated into heavier storms (%)")
    water_cap_pct: float = Field(100.0, ge=0, le=100, description="Share of today's irrigation allocation still available (%)")


class RotationSpec(BaseModel):
    """A rotation: one list of crop ids per year. [] is a fallow year."""

    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    role: str | None = None
    name: str | None = None
    years: list[list[str]] = Field(..., min_length=1, max_length=6, examples=[[["corn"], ["soybean", "cereal_rye"]]])
    tillage: Tillage | None = None


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field_id: str = Field(..., examples=["ogallala-ks"])
    priorities: Priorities | None = None
    constraints: Constraints | None = None
    scenario: Scenario | None = None
    baseline: RotationSpec | None = Field(None, description="Replace the field's baseline rotation with the farmer's own")
    custom_strategies: list[RotationSpec] | None = Field(None, max_length=4, description="Rotations built by the farmer, scored alongside")


class StressTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field_id: str
    strategies: list[RotationSpec] = Field(..., min_length=1, max_length=8)
    scenario: Scenario
    priorities: Priorities | None = None
    constraints: Constraints | None = None


class SweepRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field_id: str
    strategies: list[RotationSpec] = Field(..., min_length=1, max_length=8)
    parameter: Literal["temp_delta_c", "rain_pct", "storm_intensity_pct", "water_cap_pct"]
    steps: int = Field(7, ge=3, le=11)
    base_scenario: Scenario | None = None
    priorities: Priorities | None = None
    constraints: Constraints | None = None


class CustomFieldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(..., ge=-60, le=72)
    lon: float = Field(..., ge=-180, le=180)
    name: str | None = Field(None, max_length=80)
    area_ha: float = Field(40.0, gt=0.5, le=5000)
    irrigated: bool = False
    allocation_mm: float = Field(400.0, ge=0, le=2000)
