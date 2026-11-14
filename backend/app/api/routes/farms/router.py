"""Benchmark farms and custom fields."""
from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas.requests import CustomFieldRequest
from app.models.schemas.responses import ErrorResponse, FarmSummary, FieldOverview
from app.services import analysis, field_store

router = APIRouter(prefix="/farms", tags=["farms"])
NOT_FOUND = {404: {"model": ErrorResponse}}


@router.get("", response_model=list[FarmSummary], summary="List the benchmark farms")
def list_farms() -> list[dict]:
    """Five real fields with pre-harmonised NASA and USDA observations. Instant and offline."""
    return field_store.list_benchmarks()


@router.post("/custom", response_model=FieldOverview, responses={503: {"model": ErrorResponse}},
             summary="Build a field live from any coordinate")
def create_custom(body: CustomFieldRequest) -> dict:
    """Pulls NASA POWER, GPM IMERG, MODIS NDVI, SRTM, Daymet, SSURGO and the Cropland Data Layer
    for the coordinate (a few seconds, cached afterwards) and returns the same overview as a
    benchmark farm. The returned `id` works with every other endpoint."""
    f = field_store.create_custom_field(body.lat, body.lon, body.name, body.area_ha, body.irrigated, body.allocation_mm)
    return analysis.overview(f["id"])


@router.get("/{field_id}", response_model=FieldOverview, responses=NOT_FOUND, summary="Everything known about one field")
def get_farm(field_id: str) -> dict:
    """Farm definition, soil profile, terrain, 24-year climate summary, satellite series,
    the fusion and confidence report, hazard calendar and plain-language insights."""
    return analysis.overview(field_id)


@router.get("/{field_id}/vulnerability", responses=NOT_FOUND, summary="Bare-field and seasonal vulnerability of the current rotation")
def get_vulnerability(field_id: str) -> dict:
    """Month-by-month hazard x exposure grid for the baseline rotation, plus the MODIS NDVI check
    of the assumed crop calendar."""
    return analysis.vulnerability(field_id)
